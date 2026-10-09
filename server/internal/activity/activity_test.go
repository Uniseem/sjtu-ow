package activity

import (
	"bytes"
	"context"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func newTestDB(t *testing.T) *db.DB {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "test_activity.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatal(err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = d.Close() })
	return d
}

func TestDatesToPeriod(t *testing.T) {
	ref := time.Date(2026, 10, 9, 14, 0, 0, 0, time.UTC)

	// this_year
	p1, _ := DatesToPeriod("this_year", "", "", ref)
	if p1.Start.Month() != time.September || p1.Start.Year() != 2026 {
		t.Errorf("expected 2026-09 start, got %v", p1.Start)
	}
	if p1.End.Before(p1.Start) || p1.End.Year() != 2026 {
		t.Errorf("expected 2026 end for this_year, got %v", p1.End)
	}

	// recent_30
	p2, _ := DatesToPeriod("recent_30", "", "", ref)
	if p2.End.Before(p2.Start) {
		t.Errorf("invalid range for recent_30: %v to %v", p2.Start, p2.End)
	}

	// custom dates
	p3, _ := DatesToPeriod("custom", "2026-05-01", "2026-05-31", ref)
	if p3.Start.Day() != 1 || p3.End.Day() != 31 {
		t.Errorf("custom dates mismatch: %v to %v", p3.Start, p3.End)
	}
}

func TestGenerateCSV(t *testing.T) {
	events := []Event{
		{
			When:    time.Date(2026, 10, 5, 19, 0, 0, 0, time.UTC),
			Kind:    "内战",
			Title:   "周五内战第一场",
			Status:  "已结束",
			Entries: 12,
			Players: 10,
			URL:     "https://sjtu.example/scrims/1/",
		},
	}

	data, err := GenerateCSV(events)
	if err != nil {
		t.Fatalf("GenerateCSV failed: %v", err)
	}

	// 检查 UTF-8 BOM
	if !bytes.HasPrefix(data, []byte{0xEF, 0xBB, 0xBF}) {
		t.Errorf("expected UTF-8 BOM prefix")
	}

	csvStr := string(data)
	if !strings.Contains(csvStr, "周五内战第一场") {
		t.Errorf("CSV missing event title")
	}
	if !strings.Contains(csvStr, "内战") {
		t.Errorf("CSV missing event kind")
	}
}

func TestQueryTotalsAndEvents(t *testing.T) {
	d := newTestDB(t)
	svc := NewService(d, "https://sjtu.example")

	period := Period{
		Start: time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC),
		End:   time.Date(2026, 12, 31, 23, 59, 59, 0, time.UTC),
	}

	events, err := svc.QueryEvents(context.Background(), period)
	if err != nil {
		t.Fatalf("QueryEvents failed: %v", err)
	}
	totals, err := svc.QueryTotals(context.Background(), period, events)
	if err != nil {
		t.Fatalf("QueryTotals failed: %v", err)
	}

	// 初始空库，汇总值应当均为 0
	if totals.Members != 0 || totals.Scrims != 0 {
		t.Errorf("expected 0 totals on empty DB, got %+v", totals)
	}
}
