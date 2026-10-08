package db

import (
	"testing"
	"time"
)

func TestFormatUTCShape(t *testing.T) {
	// 北京时间 2026-10-08 15:04:05.000123 → UTC 07:04:05.000123，结尾字面 Z
	in := time.Date(2026, 10, 8, 15, 4, 5, 123000, time.FixedZone("CST", 8*3600))
	got := FormatUTC(in)
	want := "2026-10-08T07:04:05.000123Z"
	if got != want {
		t.Fatalf("FormatUTC=%q，应为 %q", got, want)
	}
}

func TestFormatUTCRoundTrip(t *testing.T) {
	for _, in := range []time.Time{
		time.Date(2026, 1, 2, 3, 4, 5, 678901000, time.UTC),
		time.Date(2020, 12, 31, 23, 59, 59, 999999000, time.FixedZone("X", -7*3600)),
		time.Unix(0, 0).UTC(),
	} {
		s := FormatUTC(in)
		back, err := ParseUTC(s)
		if err != nil {
			t.Fatalf("ParseUTC(%q): %v", s, err)
		}
		if !back.Equal(in) {
			t.Fatalf("往返不一致：%v → %q → %v", in, s, back)
		}
	}
}

// 字典序必须和时间序一致：这是把时间存成本文本的理由（12 号文档 5.6）。
func TestUTCTextSortsLikeTime(t *testing.T) {
	times := []time.Time{
		time.Date(2026, 3, 1, 0, 0, 0, 0, time.UTC),
		time.Date(2025, 12, 31, 23, 59, 59, 999999000, time.UTC),
		time.Date(2026, 3, 1, 0, 0, 0, 1, time.UTC),
		time.Date(2026, 2, 28, 12, 0, 0, 0, time.UTC),
	}
	texts := make([]string, len(times))
	for i, ts := range times {
		texts[i] = FormatUTC(ts)
	}
	for i := 1; i < len(texts); i++ {
		if times[i-1].After(times[i]) != (texts[i-1] > texts[i]) {
			t.Fatalf("文本序和时间序不一致：%q vs %q", texts[i-1], texts[i])
		}
	}
}

func TestParseUTCAcceptsLegacyShapes(t *testing.T) {
	for _, s := range []string{
		"2026-10-08T07:04:05.000123Z",
		"2026-10-08T15:04:05.000123+08:00", // 带偏移
		"2026-10-08T07:04:05Z",             // 没有微秒
	} {
		if _, err := ParseUTC(s); err != nil {
			t.Fatalf("ParseUTC(%q) 应当认：%v", s, err)
		}
	}
	if _, err := ParseUTC("前天下午"); err == nil {
		t.Fatal("乱写的值应被拒")
	}
}
