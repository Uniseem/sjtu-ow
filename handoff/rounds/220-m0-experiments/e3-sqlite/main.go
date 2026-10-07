// E3: modernc.org/sqlite under BEGIN IMMEDIATE, several processes writing one
// file (12-architecture 2 invariant 2, 5.6). Each "step" reads the counter,
// waits a little as a real check-then-write would, writes counter+1 and one log
// row, commits. Lost updates show as counter < steps done; SQLITE_BUSY shows
// as errors. Readers run alongside on a separate read-only pool.
package main

import (
	"database/sql"
	"flag"
	"fmt"
	"math/rand"
	"os"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	_ "modernc.org/sqlite"
)

func dsn(path string, write bool) string {
	tx := "immediate"
	if deferred {
		tx = "deferred"
	}
	q := "_txlock=" + tx + "&_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)&_pragma=synchronous(NORMAL)&_pragma=foreign_keys(ON)"
	if !write {
		q += "&mode=ro"
	}
	return "file:" + path + "?" + q
}

var deferred bool

// A cross-process write lock in front of BEGIN IMMEDIATE. SQLite's own busy
// handler polls, it does not queue, so a process that keeps writing can keep
// another waiting past busy_timeout; flock(2) on Linux queues its waiters.
var useFlock bool
var lockFile *os.File

func lockWrites() {
	if useFlock {
		must(syscall.Flock(int(lockFile.Fd()), syscall.LOCK_EX))
	}
}

func unlockWrites() {
	if useFlock {
		must(syscall.Flock(int(lockFile.Fd()), syscall.LOCK_UN))
	}
}

func must(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, "fatal:", err)
		os.Exit(1)
	}
}

func main() {
	mode := flag.String("mode", "work", "init | work | verify")
	path := flag.String("db", "e3.sqlite", "database file")
	steps := flag.Int("steps", 1000, "write steps per process")
	conc := flag.Int("conc", 4, "goroutines per process")
	hold := flag.Duration("hold", 200*time.Microsecond, "think time inside the write transaction")
	readers := flag.Int("readers", 2, "reader goroutines")
	flag.BoolVar(&deferred, "deferred", false, "negative control: plain BEGIN (deferred) instead of BEGIN IMMEDIATE")
	flag.BoolVar(&useFlock, "flock", false, "take a flock on <db>.wlock around every write transaction")
	flag.Parse()

	switch *mode {
	case "init":
		_ = os.Remove(*path)
		_ = os.Remove(*path + "-wal")
		_ = os.Remove(*path + "-shm")
		db, err := sql.Open("sqlite", dsn(*path, true))
		must(err)
		defer db.Close()
		_, err = db.Exec(`CREATE TABLE counter (id INTEGER PRIMARY KEY, n INTEGER NOT NULL) STRICT;
			INSERT INTO counter VALUES (1, 0);
			CREATE TABLE log (id INTEGER PRIMARY KEY, pid INTEGER NOT NULL, at TEXT NOT NULL) STRICT;`)
		must(err)
		fmt.Println("init ok")
	case "work":
		work(*path, *steps, *conc, *hold, *readers)
	case "verify":
		db, err := sql.Open("sqlite", dsn(*path, false))
		must(err)
		defer db.Close()
		var n, rows int
		must(db.QueryRow("SELECT n FROM counter WHERE id=1").Scan(&n))
		must(db.QueryRow("SELECT count(*) FROM log").Scan(&rows))
		fmt.Printf("counter=%d log_rows=%d\n", n, rows)
		if n != rows {
			fmt.Println("MISMATCH: counter and log disagree")
			os.Exit(2)
		}
	}
}

func work(path string, steps, conc int, hold time.Duration, readers int) {
	if useFlock {
		f, err := os.OpenFile(path+".wlock", os.O_CREATE|os.O_RDWR, 0o600)
		must(err)
		lockFile = f
		defer f.Close()
	}
	// Write pool: one connection, so writes inside this process queue in Go and
	// only the other processes meet the file lock.
	w, err := sql.Open("sqlite", dsn(path, true))
	must(err)
	w.SetMaxOpenConns(1)
	defer w.Close()
	r, err := sql.Open("sqlite", dsn(path, false))
	must(err)
	r.SetMaxOpenConns(4)
	defer r.Close()

	var done, failed, readsOK, readsBad atomic.Int64
	var firstErr atomic.Value
	stop := make(chan struct{})
	var rg sync.WaitGroup
	for i := 0; i < readers; i++ {
		rg.Add(1)
		go func() {
			defer rg.Done()
			for {
				select {
				case <-stop:
					return
				default:
				}
				time.Sleep(time.Millisecond) // a reader that spins starves the writers on a 4-core box
				var n int
				if err := r.QueryRow("SELECT n FROM counter WHERE id=1").Scan(&n); err != nil {
					readsBad.Add(1)
					firstErr.CompareAndSwap(nil, "read: "+err.Error())
				} else {
					readsOK.Add(1)
				}
			}
		}()
	}

	start := time.Now()
	var wg sync.WaitGroup
	per := steps / conc
	var lat sync.Mutex
	var worst time.Duration
	for g := 0; g < conc; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < per; i++ {
				t0 := time.Now()
				lockWrites()
				tx, err := w.Begin() // _txlock=immediate: BEGIN IMMEDIATE
				if err != nil {
					unlockWrites()
					failed.Add(1)
					firstErr.CompareAndSwap(nil, "begin: "+err.Error())
					continue
				}
				var n int
				if err = tx.QueryRow("SELECT n FROM counter WHERE id=1").Scan(&n); err == nil {
					time.Sleep(hold + time.Duration(rand.Intn(100))*time.Microsecond)
					_, err = tx.Exec("UPDATE counter SET n=? WHERE id=1", n+1)
				}
				if err == nil {
					_, err = tx.Exec("INSERT INTO log (pid, at) VALUES (?, ?)", os.Getpid(), time.Now().UTC().Format("2006-01-02T15:04:05.000000Z"))
				}
				if err != nil {
					_ = tx.Rollback()
					unlockWrites()
					failed.Add(1)
					firstErr.CompareAndSwap(nil, "step: "+err.Error())
					continue
				}
				if err = tx.Commit(); err != nil {
					unlockWrites()
					failed.Add(1)
					firstErr.CompareAndSwap(nil, "commit: "+err.Error())
					continue
				}
				unlockWrites()
				done.Add(1)
				d := time.Since(t0)
				lat.Lock()
				if d > worst {
					worst = d
				}
				lat.Unlock()
			}
		}()
	}
	wg.Wait()
	close(stop)
	rg.Wait()
	el := time.Since(start)
	fmt.Printf("pid=%d done=%d failed=%d reads_ok=%d reads_bad=%d elapsed=%s rate=%.0f/s worst_step=%s first_err=%v\n",
		os.Getpid(), done.Load(), failed.Load(), readsOK.Load(), readsBad.Load(), el.Round(time.Millisecond),
		float64(done.Load())/el.Seconds(), worst.Round(time.Millisecond), firstErr.Load())
}
