package search

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

func TestSearchLegacyGolden(t *testing.T) {
	raw, err := os.ReadFile("testdata/legacy_search.json")
	if err != nil {
		t.Fatal(err)
	}
	var rows []struct {
		Raw, Text, Query, Excerpt string
		Terms                     []string
		Matches                   bool
	}
	if err := json.Unmarshal(raw, &rows); err != nil {
		t.Fatal(err)
	}
	for i, row := range rows {
		t.Run(fmt.Sprint(i), func(t *testing.T) {
			q, terms := parseQuery(row.Raw)
			if q != row.Query || strings.Join(terms, "\x00") != strings.Join(row.Terms, "\x00") {
				t.Fatalf("parse: %q %v vs %q %v", q, terms, row.Query, row.Terms)
			}
			if got := excerpt(row.Text, terms); got != row.Excerpt {
				t.Fatalf("excerpt=%q want=%q", got, row.Excerpt)
			}
			if got := matches(row.Text, terms); got != row.Matches {
				t.Fatalf("matches=%v want=%v", got, row.Matches)
			}
		})
	}
}

func writeSearch(t *testing.T, d *db.DB, q string, args ...any) {
	t.Helper()
	if err := d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error { _, err := tx.ExecContext(ctx, q, args...); return err }); err != nil {
		t.Fatal(err)
	}
}

func TestSearchGroupsScopeOrderAndMetadata(t *testing.T) {
	d := newTestDB(t)
	now := "2026-10-10T00:00:00.000000Z"
	writeSearch(t, d, `INSERT INTO article_categories (id,name,slug,created_at,updated_at) VALUES (1,'资讯','news',?,?)`, now, now)
	// Equal-title articles have the reverse first/last publication order.
	for _, row := range []struct {
		id           int
		live, public int
		first, last  string
		category     any
	}{
		{1, 1, 1, "2026-10-01T00:00:00Z", "2026-10-09T00:00:00Z", 1},
		{2, 1, 1, "2026-10-09T00:00:00Z", "2026-10-01T00:00:00Z", nil},
		{3, 0, 1, now, now, nil}, {4, 1, 0, now, now, nil},
	} {
		writeSearch(t, d, `INSERT INTO pages (id,kind,slug,title,live,search_public,first_published_at,last_published_at,created_at,updated_at) VALUES (?,'article',?,'文章标题',?,?,?,?,?,?)`, row.id, fmt.Sprint(row.id), row.live, row.public, row.first, row.last, now, now)
		writeSearch(t, d, `INSERT INTO articles (page_id,category_id,summary,body_plain,body_md,search_text) VALUES (?,?,'摘要','Straße 社区正文','[泄露地址](https://secret.test)','outdated index')`, row.id, row.category)
	}
	for _, table := range []string{"tournaments", "scrims"} {
		for id, status := range []string{"published", "finished", "cancelled", "draft"} {
			writeSearch(t, d, fmt.Sprintf(`INSERT INTO %s (id,title,description,description_plain,status,created_at,updated_at) VALUES (?,'活动标题','秘密网址 secret-event.test','Straße 社区活动',?,?,?)`, table), id+10, status, now, fmt.Sprintf("2026-10-%02dT00:00:00.000000Z", id+1))
		}
	}
	writeSearch(t, d, `INSERT INTO teams (id,name,description,is_recruiting,disbanded_at,created_at,updated_at) VALUES
        (1,'Straße 社区战队','队伍简介',1,NULL,?,?),
        (2,'另一队','Straße 社区招新',0,NULL,?,?),
        (3,'Straße 社区散伙','不应出现',1,?, ?, ?)`, now, "2026-10-09T00:00:00Z", now, "2026-10-01T00:00:00Z", now, now, now)
	for _, u := range []struct {
		id       int
		nick     string
		active   int
		verified any
	}{
		{1, "Straße 社区 B", 1, now}, {2, "Straße 社区 A", 1, now}, {3, "Straße 社区停用", 0, now}, {4, "Straße 社区未验证", 1, nil}, {5, "其他人", 1, now},
	} {
		writeSearch(t, d, `INSERT INTO users (id,email,email_norm,password_hash,nickname,is_sjtu,is_active,email_verified_at,motto,agreed_terms_at,agreed_cross_border_at,created_at,updated_at) VALUES (?,?,?,'hash',?,1,?,?,'Straße 社区私人宣言',?,?,?,?)`, u.id, fmt.Sprintf("secret%d@example.test", u.id), fmt.Sprintf("secret%d@example.test", u.id), u.nick, u.active, u.verified, now, now, now, now)
	}
	res, err := NewService(d).Search(context.Background(), "STRASSE 社区")
	if err != nil {
		t.Fatal(err)
	}
	keys := []string{}
	for _, g := range res.Groups {
		keys = append(keys, g.Key)
	}
	if !reflect.DeepEqual(keys, []string{"articles", "events", "teams", "members"}) {
		t.Fatalf("groups=%v", keys)
	}
	want := [][]string{{"/news/1/", "/news/2/"}, {"/tournaments/11/", "/tournaments/10/", "/scrims/11/", "/scrims/10/"}, {"/teams/1/", "/teams/2/"}, {"/members/2/", "/members/1/"}}
	for i, g := range res.Groups {
		urls := []string{}
		for _, hit := range g.Hits {
			urls = append(urls, hit.URL)
			if hit.Title == "" || hit.Excerpt == "" || hit.Meta == "" {
				t.Fatalf("empty hit: %+v", hit)
			}
		}
		if !reflect.DeepEqual(urls, want[i]) || g.Truncated {
			t.Fatalf("group %s=%v truncated=%v", g.Key, urls, g.Truncated)
		}
	}
	if res.Groups[0].Hits[0].Meta != "资讯" || res.Groups[0].Hits[1].Meta != "文章" || res.Groups[2].Hits[0].Meta != "招募中" || res.Groups[2].Hits[1].Meta != "战队" {
		t.Fatalf("tags=%+v", res.Groups)
	}
	if res.Groups[3].Hits[0].Excerpt != "Straße 社区私人宣言" {
		t.Fatalf("motto=%q", res.Groups[3].Hits[0].Excerpt)
	}
	for _, q := range []string{"secret@example.test", "secret-event.test", "secret.test", "私人宣言", "STRASSE 无法命中"} {
		res, err := NewService(d).Search(context.Background(), q)
		if err != nil {
			t.Fatal(err)
		}
		for _, g := range res.Groups {
			if len(g.Hits) > 0 {
				t.Fatalf("private/raw Markdown matched %q: %+v", q, g)
			}
		}
	}
}

func TestSearchGroupLimits(t *testing.T) {
	for _, count := range []int{20, 21} {
		t.Run(fmt.Sprint(count), func(t *testing.T) {
			d := newTestDB(t)
			now := "2026-10-10T00:00:00.000000Z"
			for id := 1; id <= count; id++ {
				writeSearch(t, d, `INSERT INTO pages (id,kind,slug,title,live,last_published_at,created_at,updated_at) VALUES (?,'article',?,'关键词文章',1,?,?,?)`, id, fmt.Sprint(id), now, now, now)
				writeSearch(t, d, `INSERT INTO articles (page_id) VALUES (?)`, id)
				writeSearch(t, d, `INSERT INTO teams (id,name,created_at,updated_at) VALUES (?,?,?,?)`, id, fmt.Sprintf("关键词战队%d", id), now, now)
				writeSearch(t, d, `INSERT INTO users (id,email,email_norm,password_hash,nickname,is_active,email_verified_at,agreed_terms_at,agreed_cross_border_at,created_at,updated_at) VALUES (?,?,?,'h',?,1,?,?,?,?,?)`, id, fmt.Sprint(id), fmt.Sprint(id), fmt.Sprintf("关键词成员%d", id), now, now, now, now, now)
				table := "scrims"
				if id <= 10 {
					table = "tournaments"
				}
				writeSearch(t, d, fmt.Sprintf(`INSERT INTO %s (id,title,status,created_at,updated_at) VALUES (?,'关键词活动','published',?,?)`, table), id, now, now)
			}
			res, err := NewService(d).Search(context.Background(), "关键词")
			if err != nil {
				t.Fatal(err)
			}
			for _, g := range res.Groups {
				if len(g.Hits) != 20 || g.Truncated != (count > 20) {
					t.Fatalf("count=%d group=%+v", count, g)
				}
			}
			if res.Groups[1].Hits[0].Meta != "赛事" || res.Groups[1].Hits[10].Meta != "内战" {
				t.Fatal("events no longer tournaments then scrims")
			}
		})
	}
}

func TestSearchEmptyNoDatabaseAndFailure(t *testing.T) {
	d := newTestDB(t)
	svc := NewService(d)
	if err := d.Close(); err != nil {
		t.Fatal(err)
	}
	res, err := svc.Search(context.Background(), "\n \t")
	if err != nil || len(res.Groups) != 4 {
		t.Fatalf("empty=%+v err=%v", res, err)
	}
	for _, g := range res.Groups {
		if g.Hits == nil || len(g.Hits) != 0 {
			t.Fatalf("empty hits=%+v", g)
		}
	}
	if _, err := svc.Search(context.Background(), "真实查询"); err == nil {
		t.Fatal("closed database returned success")
	}
}

func TestSearchHTTPGroupsAndRateLimit(t *testing.T) {
	d := newTestDB(t)
	reg := &api.Registry{}
	NewModule(NewService(d)).Routes(reg)
	h := reg.Handler(func(*http.Request) *app.Viewer { return nil }, api.WithLimiter(ratelimit.NewEnforcer(d, clock.Fixed(time.Date(2026, 10, 10, 0, 0, 0, 0, time.UTC)))))
	for i := 0; i < 31; i++ {
		rec := httptest.NewRecorder()
		req := httptest.NewRequest(http.MethodGet, "/api/search?q=hello", nil)
		req.RemoteAddr = "192.0.2.10:1234"
		h.ServeHTTP(rec, req)
		if i < 30 {
			if rec.Code != 200 {
				t.Fatalf("request %d: %d %s", i, rec.Code, rec.Body.String())
			}
			var out Result
			if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
				t.Fatal(err)
			}
			if out.Query != "hello" || len(out.Groups) != 4 || out.Groups[0].Hits == nil {
				t.Fatalf("HTTP groups=%+v", out)
			}
		} else if rec.Code != 429 || rec.Header().Get("Retry-After") == "" {
			t.Fatalf("over limit: %d headers=%v", rec.Code, rec.Header())
		}
	}
}
