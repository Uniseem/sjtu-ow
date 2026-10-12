package activity

import (
	"context"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"strings"
	"testing"
	"time"
)

func TestActivityTotalsUseLiveArticleColumnAndPropagateDatabaseErrors(t *testing.T) {
	d := newTestDB(t)
	svc := NewService(d, "")
	at := db.FormatUTC(time.Date(2026, 10, 10, 1, 0, 0, 0, time.UTC))
	_, err := d.WritePool().Exec(`INSERT INTO pages(id,kind,title,slug,live,first_published_at,created_at,updated_at) VALUES(100,'article','统计文章','counted',1,?,?,?)`, at, at, at)
	if err != nil {
		t.Fatal(err)
	}
	period, _ := DatesToPeriod("", "2026-10-01", "2026-10-12", time.Now())
	totals, err := svc.QueryTotals(context.Background(), period, nil)
	if err != nil {
		t.Fatal(err)
	}
	if totals.Articles != 1 {
		t.Fatalf("live article count=%d", totals.Articles)
	}
	canceled, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err = svc.QueryTotals(canceled, period, nil); err == nil {
		t.Fatal("query failure was presented as zero totals")
	}
}

func TestActivityCSVNeutralizesFormulaTitlesAndUsesShanghaiTime(t *testing.T) {
	data, err := GenerateCSV([]Event{{Title: " \t=HYPERLINK(1)", When: time.Date(2026, 10, 10, 0, 0, 0, 0, time.UTC)}})
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(data), "' \t=HYPERLINK(1)") {
		t.Fatal("formula title was not neutralized")
	}
	if !strings.Contains(string(data), "2026-10-10 08:00") {
		t.Fatal("CSV timestamp omitted Shanghai timezone")
	}
}

func TestActivityPeriodRejectsPartialAndOutOfRangeDates(t *testing.T) {
	now := time.Date(2026, 10, 10, 0, 0, 0, 0, time.UTC)
	for _, params := range [][2]string{{"2026-10-01", ""}, {"1999-12-31", "2026-10-10"}, {"2026-10-01", "2101-01-01"}} {
		period, notice := DatesToPeriod("", params[0], params[1], now)
		if notice == "" || period.Start.Year() != 2026 || period.Start.Month() != time.September {
			t.Fatalf("invalid range accepted: %v %+v %q", params, period, notice)
		}
	}
}
