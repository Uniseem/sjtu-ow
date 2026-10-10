package auth

import (
	"context"
	"sync"
	"testing"
	"time"
)

func TestSessionNoticeConsumedOnce(t *testing.T) {
	d := newAuthDB(t)
	clk := &testClock{t: time.Date(2026, 10, 10, 12, 0, 0, 0, time.UTC)}
	s := NewStore(d, clk)
	ctx := context.Background()
	token, err := s.CreateWithNotice(ctx, 7, "欢迎加入社区")
	if err != nil {
		t.Fatal(err)
	}
	other, err := s.CreateWithNotice(ctx, 8, "另一个成员")
	if err != nil {
		t.Fatal(err)
	}
	var wg sync.WaitGroup
	results := make(chan string, 4)
	for range 4 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			message, err := s.PopNotice(ctx, token)
			if err != nil {
				t.Error(err)
			}
			results <- message
		}()
	}
	wg.Wait()
	close(results)
	count := 0
	for message := range results {
		if message == "欢迎加入社区" {
			count++
		}
	}
	if count != 1 {
		t.Fatalf("并发读取只应消费一次，实际 %d 次", count)
	}
	if notice, err := s.PopNotice(ctx, other); err != nil || notice != "另一个成员" {
		t.Fatalf("不应消费另一个会话的提示：%q %v", notice, err)
	}
	late, err := s.CreateWithNotice(ctx, 7, "已过期提示")
	if err != nil {
		t.Fatal(err)
	}
	clk.t = clk.t.Add(SessionTTL)
	if notice, err := s.PopNotice(ctx, late); err != nil || notice != "" {
		t.Fatalf("过期会话不能返回提示：%q %v", notice, err)
	}
}
