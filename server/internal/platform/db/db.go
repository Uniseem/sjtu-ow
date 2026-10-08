// Package db 是 SQLite 的两个连接池和唯一的写入口 WriteTx（12 号文档 5.6）。
//
// 写的规矩：
//   - 进程内：写池只有一条连接，且 WriteTx 全程持有进程互斥量；
//   - 进程间（api 和 worker 两个容器）：对 <库>.wlock 先拿 flock(LOCK_EX) 再
//     BEGIN IMMEDIATE。光靠 SQLite 的 busy_timeout 能保证不丢更新，但忙等是
//     轮询不是排队，一个持续写的进程能把另一个等过超时（220 轮 E3 实测）；
//     flock 由内核排队，同样的负载零 busy。
//
// 注意：flock 按「打开的文件描述符」记账，同一个进程里多个 goroutine 共用
// 本进程打开的这一个 wlock 文件，互相之间挡不住，所以进程内必须靠上面的互斥量；
// 也因此互斥量必须罩住从 flock 到放锁的整段，不能只罩 flock 调用本身。
package db

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"runtime"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	_ "modernc.org/sqlite" // 纯 Go 的 SQLite 驱动，注册 driver 名 "sqlite"
)

// DB 持有两个连接池和跨进程写锁。零值不可用，一律 Open。
type DB struct {
	write    *sql.DB // MaxOpenConns(1)，_txlock=immediate
	read     *sql.DB // mode=ro
	lockFile *os.File
	mu       sync.Mutex // 见包注释：进程内的写串行
	wd       watchdog
	path     string
}

// Tx 是 WriteTx 交给业务函数的写事务。后续里程碑的 jobs.Enqueue、outbox.Send
// 都挂在它身上。
type Tx struct{ *sql.Tx }

// Option 配置 Open。
type Option func(*DB)

// WithWatchdog 覆盖看门狗阈值：failAfter > 0 时写事务超过它就回滚并报错
// （开发和测试用），warnAfter > 0 时超过它记一条警告（生产用），0 表示关。
func WithWatchdog(failAfter, warnAfter time.Duration) Option {
	return func(d *DB) { dwd := watchdog{failAfter: failAfter, warnAfter: warnAfter}; d.wd = dwd }
}

// DefaultDev 是开发和测试的看门狗：超过 1 秒失败（12 号文档 5.6）。
func DefaultDev() Option { return WithWatchdog(time.Second, 0) }

// DefaultProd 是生产的看门狗：超过 200 毫秒记警告。最终数值等导入后的真实
// 事务时长分布再定（13 号文档 C 节）。
func DefaultProd() Option { return WithWatchdog(0, 200*time.Millisecond) }

func dsn(path string, write bool) string {
	q := "_txlock=immediate&_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)" +
		"&_pragma=synchronous(NORMAL)&_pragma=foreign_keys(ON)"
	if !write {
		q += "&mode=ro"
	}
	return "file:" + path + "?" + q
}

// Open 打开两个连接池并建好跨进程锁文件。opts 缺省用 DefaultDev。
func Open(path string, opts ...Option) (*DB, error) {
	d := &DB{path: path, wd: watchdog{failAfter: time.Second}}
	for _, opt := range opts {
		opt(d)
	}

	// 写池先开：mode=ro 的读池要求库文件已经存在，写池第一条连接负责建库。
	w, err := sql.Open("sqlite", dsn(path, true))
	if err != nil {
		return nil, fmt.Errorf("打开写池：%w", err)
	}
	w.SetMaxOpenConns(1)
	w.SetMaxIdleConns(1)
	if err := w.Ping(); err != nil {
		_ = w.Close()
		return nil, fmt.Errorf("连不上数据库 %s：%w", path, err)
	}
	r, err := sql.Open("sqlite", dsn(path, false))
	if err != nil {
		_ = w.Close()
		return nil, fmt.Errorf("打开读池：%w", err)
	}
	r.SetMaxOpenConns(readPoolSize())
	r.SetMaxIdleConns(readPoolSize())

	lock, err := os.OpenFile(path+".wlock", os.O_CREATE|os.O_RDWR, 0o600)
	if err != nil {
		_ = w.Close()
		_ = r.Close()
		return nil, fmt.Errorf("建写锁文件：%w", err)
	}

	d.write, d.read, d.lockFile = w, r, lock
	return d, nil
}

func readPoolSize() int {
	n := 4
	if cpu := runtime.NumCPU(); cpu < n {
		n = cpu
	}
	return n
}

// Close 关掉两个池和锁文件。
func (d *DB) Close() error {
	var firstErr error
	for _, err := range []error{d.write.Close(), d.read.Close(), d.lockFile.Close()} {
		if err != nil && firstErr == nil {
			firstErr = err
		}
	}
	return firstErr
}

// ReadPool 给只读查询用。查询预算测试用 Counted 包一层计数。
func (d *DB) ReadPool() *sql.DB { return d.read }

// WritePool 只给迁移这类一次性管理操作用；业务写一律走 WriteTx。
func (d *DB) WritePool() *sql.DB { return d.write }

// ErrSlowTx 表示写事务超过看门狗的失败阈值，已被回滚。
var ErrSlowTx = errors.New("写事务超过看门狗阈值，已回滚")

// WriteTx 是全站唯一的写入口：拿进程互斥量和跨进程 flock，开 IMMEDIATE
// 事务跑 fn，提交或回滚，放锁。fn 里不要再嵌套 WriteTx（会死锁）。
// fn 返回后先判超时再提交：不理会 ctx 取消、慢慢做完的事务也不会落库。
func (d *DB) WriteTx(ctx context.Context, fn func(context.Context, *Tx) error) error {
	d.mu.Lock()
	defer d.mu.Unlock()

	start := time.Now()
	var fired atomic.Bool
	if d.wd.failAfter > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithCancel(ctx)
		defer cancel()
		timer := time.AfterFunc(d.wd.failAfter, func() {
			fired.Store(true)
			cancel() // 让 fn 里正在跑的查询尽快停
		})
		defer timer.Stop()
	}

	if err := syscall.Flock(int(d.lockFile.Fd()), syscall.LOCK_EX); err != nil {
		return fmt.Errorf("拿跨进程写锁：%w", err)
	}
	defer func() { _ = syscall.Flock(int(d.lockFile.Fd()), syscall.LOCK_UN) }()

	tx, err := d.write.BeginTx(ctx, nil) // _txlock=immediate → BEGIN IMMEDIATE
	if err != nil {
		if fired.Load() {
			return fmt.Errorf("%w（开事务前等锁超过 %s）", ErrSlowTx, d.wd.failAfter)
		}
		return fmt.Errorf("开写事务：%w", err)
	}

	fnErr := fn(ctx, &Tx{tx})
	afterFn := time.Since(start)

	if d.wd.failAfter > 0 && (afterFn > d.wd.failAfter || (fnErr != nil && fired.Load())) {
		_ = tx.Rollback()
		return fmt.Errorf("%w（%s 超过 %s）", ErrSlowTx, afterFn.Round(time.Millisecond), d.wd.failAfter)
	}
	if fnErr != nil {
		_ = tx.Rollback()
		return fnErr
	}
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("提交写事务：%w", err)
	}
	if w := d.wd.warnAfter; w > 0 {
		if total := time.Since(start); total > w {
			slog.WarnContext(ctx, "写事务偏慢", "elapsed", total.String(), "threshold", w.String())
		}
	}
	return nil
}
