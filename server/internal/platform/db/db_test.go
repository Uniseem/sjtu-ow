package db

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"testing"
	"time"
)

// 两进程并发写测试里子进程跑的步数（父子两边要一致）。
const childSteps = 300

// 测试进程可以 re-exec 自己当第二个写进程（SJTUOW_TX_CHILD=1，
// 或 SJTUOW_TX_HOLD=1 做长持锁），这是 M1 完成标准里「两进程并发写测试」
// 的做法（种子是 220 轮的 E3）。
func TestMain(m *testing.M) {
	switch {
	case os.Getenv("SJTUOW_TX_CHILD") == "1":
		childRun()
	case os.Getenv("SJTUOW_TX_HOLD") == "1":
		childHold()
	}
	os.Exit(m.Run())
}

// childHold 在写事务里握锁 7 秒（超过 busy_timeout 的 5 秒）再提交。
func childHold() {
	path := os.Getenv("SJTUOW_TX_DB")
	d, err := Open(path, WithWatchdog(30*time.Second, 0))
	if err != nil {
		fmt.Fprintln(os.Stderr, "child open:", err)
		os.Exit(1)
	}
	defer d.Close()
	err = d.WriteTx(context.Background(), func(ctx context.Context, tx *Tx) error {
		time.Sleep(7 * time.Second)
		_, err := tx.ExecContext(ctx, "INSERT INTO log (pid) VALUES (?)", os.Getpid())
		return err
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, "child hold:", err)
		os.Exit(1)
	}
	os.Exit(0)
}

func childRun() {
	path := os.Getenv("SJTUOW_TX_DB")
	d, err := Open(path, WithWatchdog(10*time.Second, 0)) // 子进程关掉看门狗，只测并发正确性
	if err != nil {
		fmt.Fprintln(os.Stderr, "child open:", err)
		os.Exit(1)
	}
	defer d.Close()
	ctx := context.Background()
	for i := 0; i < childSteps; i++ {
		if err := step(ctx, d); err != nil {
			fmt.Fprintln(os.Stderr, "child step:", err)
			os.Exit(1)
		}
	}
	os.Exit(0)
}

// 一步「读—改—写」：丢更新会表现为 counter < log 行数，SQLITE_BUSY 表现为报错。
func step(ctx context.Context, d *DB) error {
	return d.WriteTx(ctx, func(ctx context.Context, tx *Tx) error {
		var n int
		if err := tx.QueryRowContext(ctx, "SELECT n FROM counter WHERE id=1").Scan(&n); err != nil {
			return err
		}
		if _, err := tx.ExecContext(ctx, "UPDATE counter SET n=? WHERE id=1", n+1); err != nil {
			return err
		}
		_, err := tx.ExecContext(ctx, "INSERT INTO log (pid) VALUES (?)", os.Getpid())
		return err
	})
}

func openTestDB(t *testing.T, opts ...Option) *DB {
	t.Helper()
	d, err := Open(filepath.Join(t.TempDir(), "test.sqlite"), opts...)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { _ = d.Close() })
	return d
}

func initScratch(t *testing.T, d *DB) {
	t.Helper()
	ctx := context.Background()
	err := d.WriteTx(ctx, func(ctx context.Context, tx *Tx) error {
		_, err := tx.ExecContext(ctx, `CREATE TABLE counter (id INTEGER PRIMARY KEY, n INTEGER NOT NULL) STRICT;
			INSERT INTO counter VALUES (1, 0);
			CREATE TABLE log (id INTEGER PRIMARY KEY, pid INTEGER NOT NULL) STRICT;`)
		return err
	})
	if err != nil {
		t.Fatalf("建表: %v", err)
	}
}

func counts(t *testing.T, d *DB) (n, rows int) {
	t.Helper()
	ctx := context.Background()
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT n FROM counter WHERE id=1").Scan(&n); err != nil {
		t.Fatalf("读 counter: %v", err)
	}
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM log").Scan(&rows); err != nil {
		t.Fatalf("读 log: %v", err)
	}
	return
}

func TestOpenCreatesDatabaseAndReadPoolSeesIt(t *testing.T) {
	d := openTestDB(t)
	initScratch(t, d)
	if err := d.WriteTx(context.Background(), func(ctx context.Context, tx *Tx) error {
		_, err := tx.ExecContext(ctx, "UPDATE counter SET n=7 WHERE id=1")
		return err
	}); err != nil {
		t.Fatalf("写: %v", err)
	}
	n, _ := counts(t, d)
	if n != 7 {
		t.Fatalf("读池没看到写池写的数据：n=%d", n)
	}
}

func TestWriteTxRollbackOnError(t *testing.T) {
	d := openTestDB(t)
	initScratch(t, d)
	sentinel := errors.New("业务报错")
	err := d.WriteTx(context.Background(), func(ctx context.Context, tx *Tx) error {
		if _, err := tx.ExecContext(ctx, "UPDATE counter SET n=99 WHERE id=1"); err != nil {
			return err
		}
		return sentinel
	})
	if !errors.Is(err, sentinel) {
		t.Fatalf("应把业务错误原样带出，得到 %v", err)
	}
	n, _ := counts(t, d)
	if n != 0 {
		t.Fatalf("回滚失败：n=%d（应为 0）", n)
	}
}

// 同进程里并发写靠互斥量 + 单连接写池串行：不丢更新、零失败。
func TestWriteTxSerializesGoroutines(t *testing.T) {
	d := openTestDB(t, WithWatchdog(10*time.Second, 0))
	initScratch(t, d)

	const goroutines, steps = 8, 40
	var wg sync.WaitGroup
	errs := make(chan error, goroutines*steps)
	for g := 0; g < goroutines; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < steps; i++ {
				if err := step(context.Background(), d); err != nil {
					errs <- err
				}
			}
		}()
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		t.Fatalf("并发写失败：%v", err)
	}
	n, rows := counts(t, d)
	if want := goroutines * steps; n != want || rows != want {
		t.Fatalf("丢更新：counter=%d log=%d，都应是 %d", n, rows, want)
	}
}

// 两个进程（测试进程 re-exec 自己）加本进程三方并发：flock + IMMEDIATE 下
// 零 SQLITE_BUSY、零丢更新。对照组（不用 IMMEDIATE / 不加 flock 必出 busy）
// 是 220 轮 E3 的结论，不在每次测试里重跑。
func TestWriteTxTwoProcesses(t *testing.T) {
	if testing.Short() {
		t.Skip("两进程压测不进 -short")
	}
	dir := t.TempDir()
	path := filepath.Join(dir, "two.sqlite")

	d, err := Open(path, WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer d.Close()
	initScratch(t, d)

	const childSteps = 300
	const parentGoroutines = 4
	const parentSteps = 200 // 每个 goroutine

	self, err := os.Executable()
	if err != nil {
		t.Fatalf("找测试二进制：%v", err)
	}
	var wg sync.WaitGroup
	for i := 0; i < 2; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			cmd := exec.Command(self)
			cmd.Env = append(os.Environ(), "SJTUOW_TX_CHILD=1", "SJTUOW_TX_DB="+path)
			out, err := cmd.CombinedOutput()
			if err != nil {
				t.Errorf("子进程退出 %v：%s", err, out)
			}
		}()
	}
	for g := 0; g < parentGoroutines; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < parentSteps; i++ {
				if err := step(context.Background(), d); err != nil {
					t.Errorf("本进程写失败：%v", err)
					return
				}
			}
		}()
	}
	wg.Wait()

	n, rows := counts(t, d)
	want := 2*childSteps + parentGoroutines*parentSteps
	if n != want || rows != want {
		t.Fatalf("丢更新：counter=%d log=%d，都应是 %d", n, rows, want)
	}
}

// flock 的「拆掉它会红」（硬规则 7）：另一个进程在写事务里握锁 7 秒
// （超过 busy_timeout 的 5 秒），本进程的写事务必须排队等到锁、成功提交，
// 而不是 5 秒后 SQLITE_BUSY。去掉跨进程 flock 只留 IMMEDIATE + busy_timeout，
// 这条测试稳定红——这正是 220 轮 E3 实测到的忙等不公平。
func TestWriteTxQueuesBehindOtherProcess(t *testing.T) {
	if testing.Short() {
		t.Skip("跨进程排队测试不进 -short")
	}
	dir := t.TempDir()
	path := filepath.Join(dir, "hold.sqlite")
	d, err := Open(path, WithWatchdog(30*time.Second, 0))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer d.Close()
	initScratch(t, d)

	self, err := os.Executable()
	if err != nil {
		t.Fatalf("找测试二进制：%v", err)
	}
	cmd := exec.Command(self)
	cmd.Env = append(os.Environ(), "SJTUOW_TX_HOLD=1", "SJTUOW_TX_DB="+path)
	if err := cmd.Start(); err != nil {
		t.Fatalf("起子进程：%v", err)
	}
	defer func() { _ = cmd.Wait() }()

	time.Sleep(1500 * time.Millisecond) // 等孩子确实进了写事务
	err = d.WriteTx(context.Background(), func(ctx context.Context, tx *Tx) error {
		_, err := tx.ExecContext(ctx, "INSERT INTO log (pid) VALUES (?)", os.Getpid())
		return err
	})
	if err != nil {
		t.Fatalf("应排队等到锁而不是报错：%v", err)
	}
	_ = cmd.Wait()
	_, rows := counts(t, d)
	if rows != 2 {
		t.Fatalf("两边各写的一行都该在库里：rows=%d（应为 2）", rows)
	}
}

// 开发和测试模式：慢事务在提交前被拦下、回滚、报 ErrSlowTx。
// fn 故意不理会 ctx 的取消（先睡再查），验证「慢慢做完也不落库」。
func TestWatchdogFailsSlowTxBeforeCommit(t *testing.T) {
	d := openTestDB(t, WithWatchdog(150*time.Millisecond, 0))
	initScratch(t, d)

	err := d.WriteTx(context.Background(), func(ctx context.Context, tx *Tx) error {
		time.Sleep(400 * time.Millisecond)
		_, err := tx.ExecContext(ctx, "UPDATE counter SET n=42 WHERE id=1")
		return err // ctx 已被看门狗取消，这里多半是 context.Canceled；就算成功也会被拦
	})
	if !errors.Is(err, ErrSlowTx) {
		t.Fatalf("应报 ErrSlowTx，得到 %v", err)
	}
	n, _ := counts(t, d)
	if n != 0 {
		t.Fatalf("慢事务的数据落了库：n=%d（应为 0）", n)
	}
}

// 生产模式：只记警告、不拦事务。日志用自定义 handler 接住验证。
func TestWatchdogWarnsButCommits(t *testing.T) {
	d := openTestDB(t, WithWatchdog(0, 100*time.Millisecond))
	initScratch(t, d)

	rec := &recordHandler{}
	old := setSlogHandler(rec)
	defer setSlogHandler(old)

	err := d.WriteTx(context.Background(), func(ctx context.Context, tx *Tx) error {
		time.Sleep(250 * time.Millisecond)
		_, err := tx.ExecContext(ctx, "UPDATE counter SET n=5 WHERE id=1")
		return err
	})
	if err != nil {
		t.Fatalf("警告模式不该拦事务：%v", err)
	}
	n, _ := counts(t, d)
	if n != 5 {
		t.Fatalf("数据没提交：n=%d", n)
	}
	if rec.warns == 0 {
		t.Fatal("没记到警告日志")
	}
}

func TestMigrationIdempotent(t *testing.T) {
	d := openTestDB(t)
	ctx := context.Background()
	if err := Migrate(ctx, d); err != nil {
		t.Fatalf("迁移: %v", err)
	}
	v1, err := Version(ctx, d)
	if err != nil || v1 < 1 {
		t.Fatalf("迁移后版本应是 >=1，得到 %d（err=%v）", v1, err)
	}
	if err := Migrate(ctx, d); err != nil {
		t.Fatalf("重复迁移应是无操作: %v", err)
	}
	v2, _ := Version(ctx, d)
	if v2 != v1 {
		t.Fatalf("重复迁移改了版本：%d → %d", v1, v2)
	}
	var tables int
	if err := d.ReadPool().QueryRowContext(ctx,
		"SELECT count(*) FROM sqlite_master WHERE type='table' AND name='goose_db_version'").Scan(&tables); err != nil {
		t.Fatalf("查版本表: %v", err)
	}
	if tables != 1 {
		t.Fatal("goose 的版本表没建出来")
	}
}

func TestCounterCountsQueries(t *testing.T) {
	d := openTestDB(t)
	initScratch(t, d)
	ctx := context.Background()

	// 读语句包读池、写语句包写池：查询预算测试数的就是这两类。
	var c Counter
	reads := c.Counted(d.ReadPool())
	if _, err := reads.QueryContext(ctx, "SELECT n FROM counter WHERE id=1"); err != nil {
		t.Fatal(err)
	}
	if err := reads.QueryRowContext(ctx, "SELECT count(*) FROM log").Scan(new(int)); err != nil {
		t.Fatal(err)
	}
	writes := c.Counted(d.WritePool())
	if _, err := writes.ExecContext(ctx, "DELETE FROM log WHERE id=-1"); err != nil {
		t.Fatal(err)
	}
	if got := c.Count(); got != 3 {
		t.Fatalf("数到的语句 %d，应为 3", got)
	}
}
