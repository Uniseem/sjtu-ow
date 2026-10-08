package clock

import (
	"testing"
	"time"
)

func TestFixedAlwaysReturnsSameTime(t *testing.T) {
	want := time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)
	c := Fixed(want)
	for i := 0; i < 3; i++ {
		if got := c.Now(); !got.Equal(want) {
			t.Fatalf("Fixed 返回了 %v，应为 %v", got, want)
		}
	}
}

func TestSystemIsCloseToNow(t *testing.T) {
	before := time.Now()
	got := System{}.Now()
	after := time.Now()
	if got.Before(before) || got.After(after) {
		t.Fatalf("System.Now() 应落在调用前后之间：%v", got)
	}
}
