// txhammer 用真实的 WriteTx 压并发写（220 轮 E3 的后继）。两个用途：
//   - go test 里两进程并发写测试的对照组由测试自己 re-exec 完成；
//   - 222 轮在测试机上用 Docker 起两个容器挂同一个数据卷各压一轮，
//     证实跨容器的 flock 有效（13 号文档 C 节）。
//
// 用法：txhammer -mode init|work|verify -db 路径 [-steps N] [-conc N] [-hold 时长]
package main

import (
	"context"
	"flag"
	"fmt"
	"math/rand"
	"os"
	"sync"
	"sync/atomic"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func main() {
	mode := flag.String("mode", "work", "init | work | verify")
	path := flag.String("db", "hammer.sqlite", "数据库文件")
	steps := flag.Int("steps", 1000, "每个进程的写步数")
	conc := flag.Int("conc", 4, "并发 goroutine 数")
	hold := flag.Duration("hold", 200*time.Microsecond, "写事务里的思考时间")
	flag.Parse()

	switch *mode {
	case "init":
		must(initSchema(*path))
		fmt.Println("init ok")
	case "work":
		work(*path, *steps, *conc, *hold)
	case "verify":
		n, rows, err := verify(*path)
		must(err)
		fmt.Printf("counter=%d log_rows=%d\n", n, rows)
		if n != rows {
			fmt.Println("MISMATCH: counter 和 log 对不上")
			os.Exit(2)
		}
	}
}

func must(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, "fatal:", err)
		os.Exit(1)
	}
}

func open(path string) *db.DB {
	d, err := db.Open(path, db.DefaultDev())
	must(err)
	return d
}

func initSchema(path string) error {
	for _, suffix := range []string{"", "-wal", "-shm", ".wlock"} {
		_ = os.Remove(path + suffix)
	}
	d := open(path)
	defer d.Close()
	return d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, `CREATE TABLE counter (id INTEGER PRIMARY KEY, n INTEGER NOT NULL) STRICT;
			INSERT INTO counter VALUES (1, 0);
			CREATE TABLE log (id INTEGER PRIMARY KEY, pid INTEGER NOT NULL, at TEXT NOT NULL) STRICT;`)
		return err
	})
}

// 一步 = 读计数器 → 思考一下 → 写 counter+1 和一行日志。丢更新会表现为
// counter < log 行数，SQLITE_BUSY 表现为报错。
func step(ctx context.Context, d *db.DB, hold time.Duration) error {
	return d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		var n int
		if err := tx.QueryRowContext(ctx, "SELECT n FROM counter WHERE id=1").Scan(&n); err != nil {
			return err
		}
		time.Sleep(hold + time.Duration(rand.Intn(100))*time.Microsecond)
		if _, err := tx.ExecContext(ctx, "UPDATE counter SET n=? WHERE id=1", n+1); err != nil {
			return err
		}
		_, err := tx.ExecContext(ctx, "INSERT INTO log (pid, at) VALUES (?, ?)",
			os.Getpid(), db.FormatUTC(time.Now()))
		return err
	})
}

func work(path string, steps, conc int, hold time.Duration) {
	d := open(path)
	defer d.Close()
	ctx := context.Background()

	var done, failed atomic.Int64
	var firstErr atomic.Value
	var mu sync.Mutex
	worst := time.Duration(0)
	start := time.Now()

	var wg sync.WaitGroup
	for g := 0; g < conc; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < steps/conc; i++ {
				t0 := time.Now()
				if err := step(ctx, d, hold); err != nil {
					failed.Add(1)
					firstErr.CompareAndSwap(nil, err.Error())
					continue
				}
				done.Add(1)
				mu.Lock()
				if el := time.Since(t0); el > worst {
					worst = el
				}
				mu.Unlock()
			}
		}()
	}
	wg.Wait()

	el := time.Since(start)
	fmt.Printf("pid=%d done=%d failed=%d elapsed=%s rate=%.0f/s worst_step=%s first_err=%v\n",
		os.Getpid(), done.Load(), failed.Load(), el.Round(time.Millisecond),
		float64(done.Load())/el.Seconds(), worst.Round(time.Millisecond), firstErr.Load())
	if failed.Load() > 0 {
		os.Exit(1)
	}
}

func verify(path string) (n, rows int, err error) {
	d := open(path)
	defer d.Close()
	ctx := context.Background()
	if err = d.ReadPool().QueryRowContext(ctx, "SELECT n FROM counter WHERE id=1").Scan(&n); err != nil {
		return
	}
	err = d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM log").Scan(&rows)
	return
}
