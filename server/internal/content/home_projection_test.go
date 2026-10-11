package content

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func homeFixture(t *testing.T) (*db.DB, *Service, *app.Ctx) {
	t.Helper()
	d, svc := newsFixture(t)
	projectionExec(t, d, `UPDATE site_settings SET founded_on='2020-02-29',qq_group_url='https://qm.qq.com/test',hero_image_id=20 WHERE id=1;
 UPDATE users SET email_verified_at=NULL WHERE id=2;
 INSERT INTO users (id,email,email_norm,nickname,password_hash,is_active,email_verified_at,agreed_terms_at,agreed_cross_border_at,created_at,updated_at) VALUES
 (3,'closed@test.example','closed@test.example','停用','h',0,'2026-10-10','2026-10-10','2026-10-10','2026-10-10','2026-10-10');
 INSERT INTO teams (id,name,is_recruiting,recruiting_roles,created_at,updated_at) VALUES (1,'队1',1,'tank','2026-10-10T00:00:00Z','2026-10-10T00:00:00Z');
 INSERT INTO team_memberships (team_id,user_id,role,joined_at) VALUES (1,1,'captain','2026-10-10T00:00:00Z');
 INSERT INTO home_pins VALUES (101,0),(109,1),(104,2),(105,3);
 UPDATE pages SET first_published_at='2026-10-10T09:00:00Z' WHERE id=104;
 INSERT INTO registrations (id,tournament_id,team_name,status,submitted_at,created_at,updated_at) VALUES
 (1,2,'已通过','approved','2026-10-10','2026-10-10','2026-10-10'),(2,2,'待审','pending','2026-10-10','2026-10-10','2026-10-10');
 INSERT INTO registration_members (registration_id,tournament_id,user_id,nickname,battletag,is_active) VALUES (1,2,1,'作者','Test#1',1);
 INSERT INTO scrims (id,title,status,format,starts_at,signup_closes_at,created_at,updated_at) VALUES
 (1,'未来六人内战','published','rq_6v6','2026-10-12T12:00:00Z','2026-10-10T23:00:00Z','2026-10-10','2026-10-10'),
 (2,'过去内战','published','rq_5v5','2026-10-10T23:00:00Z',NULL,'2026-10-10','2026-10-10'),
 (3,'累计内战','finished','rq_5v5','2026-10-01T00:00:00Z',NULL,'2026-10-10','2026-10-10'),
 (4,'草稿内战','draft','rq_5v5','2026-10-12T00:00:00Z',NULL,'2026-10-10','2026-10-10');
 INSERT INTO scrim_signups (scrim_id,user_id,role_tank,created_at,updated_at) VALUES (1,1,1,'2026-10-10','2026-10-10');`)
	ctx := &app.Ctx{Context: context.Background(), Clock: clock.Fixed(time.Date(2026, 10, 11, 0, 0, 0, 0, time.UTC))}
	return d, svc, ctx
}

func TestHomeProjectionAndAgenda(t *testing.T) {
	_, svc, ctx := homeFixture(t)
	out, err := svc.HomePage(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if out.Stats.MemberCount != 1 || out.Stats.TeamCount != 1 || out.Stats.ScrimsHeld != 1 || out.Stats.HeroImageID == nil || *out.Stats.HeroImageID != 20 || out.Stats.QQGroupURL != "https://qm.qq.com/test" {
		t.Fatalf("stats=%+v", out.Stats)
	}
	if len(out.Scrims) != 1 || out.Scrims[0].ID != 1 || out.Scrims[0].Capacity != 12 || out.Scrims[0].Count != 1 || out.Scrims[0].SignupOpen || out.Scrims[0].Time != "20:00" || out.Scrims[0].Weekday != "周一" {
		t.Fatalf("scrims=%+v", out.Scrims)
	}
	if len(out.News) != 4 || out.News[0].ID != 101 || !out.News[0].Pinned || out.News[1].ID != 109 || out.News[2].ID != 112 || out.News[3].ID != 108 {
		t.Fatalf("news=%+v", out.News)
	}
	if out.News[1].DefaultCoverImageID == nil || *out.News[1].DefaultCoverImageID != 30 || out.News[0].Author == nil || out.News[0].Author.ID != 1 {
		t.Fatal("card projection incomplete")
	}
	if len(out.Notices) != 3 || out.Notices[0].ID != 112 || out.Notices[1].ID != 101 || out.Notices[2].ID != 113 {
		t.Fatalf("notices=%+v", out.Notices)
	}
	if len(out.Teams) != 1 || out.Teams[0].MemberCount != 1 || !out.Teams[0].IsRecruiting || out.Teams[0].WantedRoles != "tank" || out.Teams[0].CreatedAtMonth != "2026.10" {
		t.Fatalf("teams=%+v", out.Teams)
	}
	if out.FeatureTournament == nil || out.FeatureTournament.ID != 2 || out.FeatureTournament.Phase != "open" || out.FeatureTournament.ApprovedTeams != 1 || out.FeatureTournament.DefaultCoverImageID == nil || *out.FeatureTournament.DefaultCoverImageID != 20 || out.FeatureTournament.Facts != "整队报名 · 报名截止 01.01 08:00 · 01.01 比赛 · 已通过 1 队" {
		t.Fatalf("feature=%+v", out.FeatureTournament)
	}

	if out.Agenda == nil || len(out.Agenda) != 0 {
		t.Fatal("visitor has agenda")
	}
	ctx.Viewer = &app.Viewer{ID: 1}
	out, err = svc.HomePage(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if len(out.Agenda) != 2 || out.Agenda[0].URL != "/scrims/1/" || out.Agenda[1].URL != "/registrations/1/" {
		t.Fatalf("agenda=%+v", out.Agenda)
	}
	ctx.Viewer.Disabled = true
	out, err = svc.HomePage(ctx)
	if err != nil || len(out.Agenda) != 0 {
		t.Fatal("disabled viewer has agenda")
	}
	ctx.Viewer = &app.Viewer{ID: 2}
	out, err = svc.HomePage(ctx)
	if err != nil || len(out.Agenda) != 0 {
		t.Fatal("other user has another member's agenda")
	}
	// 真实 HTTP 序列化：所有列表是数组，agenda 与独立接口是同一种投影。
	reg := &api.Registry{}
	NewModule(svc).Routes(reg)
	rec := httptest.NewRecorder()
	reg.Handler(func(*http.Request) *app.Viewer { return nil }).ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/page/home", nil))
	if rec.Code != 200 {
		t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
	}
	var raw map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &raw); err != nil {
		t.Fatal(err)
	}
	for _, key := range []string{"scrims", "news", "notices", "teams", "agenda"} {
		if _, ok := raw[key].([]any); !ok {
			t.Fatalf("%s=%v", key, raw[key])
		}
	}
}

func TestHomeFeatureChoice(t *testing.T) {
	d, svc, ctx := homeFixture(t)
	projectionExec(t, d, `UPDATE tournaments SET registration_closes_at='2026-10-20T00:00:00Z',starts_at='2026-10-25T00:00:00Z' WHERE id=2;
 INSERT INTO tournaments (id,title,status,registration_mode,starts_at,registration_opens_at,registration_closes_at,created_at,updated_at) VALUES
 (3,'最先截止','published','individual','2026-10-26T00:00:00Z','2026-10-01T00:00:00Z','2026-10-15T00:00:00Z','2026-10-10','2026-10-10'),
 (4,'即将开始','published','team','2026-10-13T00:00:00Z','2026-10-12T00:00:00Z','2026-10-13T00:00:00Z','2026-10-10','2026-10-10'),
 (5,'最近结束','finished','team','2026-10-09T00:00:00Z','2026-10-01T00:00:00Z','2026-10-05T00:00:00Z','2026-10-10','2026-10-10'),
 (6,'早已结束','finished','team','2026-10-08T00:00:00Z','2026-10-01T00:00:00Z','2026-10-04T00:00:00Z','2026-10-10','2026-10-10'),
 (7,'取消','cancelled','team','2026-10-12T00:00:00Z','2026-10-01T00:00:00Z','2026-10-12T00:00:00Z','2026-10-10','2026-10-10'),
 (8,'草稿','draft','team','2026-10-12T00:00:00Z','2026-10-01T00:00:00Z','2026-10-12T00:00:00Z','2026-10-10','2026-10-10'),
 (9,'later','published','team','2026-10-20T00:00:00Z','2026-10-19T00:00:00Z','2026-10-20T00:00:00Z','2026-10-10','2026-10-10');`)
	check := func(id int64, phase string) {
		t.Helper()
		out, err := svc.HomePage(ctx)
		if err != nil {
			t.Fatal(err)
		}
		if out.FeatureTournament == nil || out.FeatureTournament.ID != id || out.FeatureTournament.Phase != phase {
			t.Fatalf("feature=%+v want=%d %s", out.FeatureTournament, id, phase)
		}
	}
	check(3, "open")
	projectionExec(t, d, "UPDATE tournaments SET status='finished' WHERE id IN (2,3)")
	check(4, "upcoming")
	projectionExec(t, d, "UPDATE tournaments SET status='finished' WHERE id IN (4,9)")
	check(3, "finished")
	projectionExec(t, d, "UPDATE tournaments SET status='draft' WHERE id IN (2,3,4,9)")
	check(5, "finished")
	ctx.Clock = clock.Fixed(time.Date(2026, 10, 14, 0, 0, 0, 0, time.UTC))
	projectionExec(t, d, "UPDATE tournaments SET status='published' WHERE id=4")
	check(4, "closed")
	projectionExec(t, d, "UPDATE tournaments SET status='draft' WHERE id IN (4,5,6)")
	out, err := svc.HomePage(ctx)
	if err != nil || out.FeatureTournament != nil {
		t.Fatal("no public candidate must be nil")
	}
}

func TestHomeAgeAndQueryFailures(t *testing.T) {
	loc, err := time.LoadLocation("Asia/Shanghai")
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		raw, now    string
		years, days int
		nilAge      bool
	}{
		{"2020-02-29", "2021-02-28T00:00:00Z", 1, 0, false},
		{"2020-02-29", "2024-02-29T00:00:00Z", 4, 0, false},
		{"2020-10-11", "2026-10-10T16:30:00Z", 6, 0, false},
		{"2030-01-01", "2026-10-11T00:00:00Z", 0, 0, true},
		{"", "2026-10-11T00:00:00Z", 0, 0, true},
	} {
		now, _ := time.Parse(time.RFC3339, tc.now)
		age, err := communityAge(tc.raw, now, loc)
		if err != nil {
			t.Fatal(err)
		}
		if (age == nil) != tc.nilAge || (age != nil && (age.Years != tc.years || age.Days != tc.days)) {
			t.Fatalf("age=%+v tc=%+v", age, tc)
		}
	}
	for _, table := range []string{"users", "teams", "scrims", "site_settings", "image_collections", "tournaments", "registrations", "articles", "article_categories", "home_pins", "team_memberships"} {
		t.Run(table, func(t *testing.T) {
			d, svc, ctx := homeFixture(t)
			projectionExec(t, d, "ALTER TABLE "+table+" RENAME TO broken_"+table)
			if _, err := svc.HomePage(ctx); err == nil {
				t.Fatal("query error swallowed")
			}
		})
	}
}

func TestHomeLimitsAndPinnedDedup(t *testing.T) {
	d, svc, ctx := homeFixture(t)
	for i := 0; i < 7; i++ {
		projectionExec(t, d, `INSERT INTO scrims (id,title,status,format,starts_at,created_at,updated_at) VALUES (?,?,'published','rq_5v5',?,'2026-10-10','2026-10-10')`, 10+i, fmt.Sprintf("future %d", i), fmt.Sprintf("2026-11-%02dT00:00:00Z", i+1))
		projectionExec(t, d, `INSERT INTO teams (id,name,created_at,updated_at) VALUES (?,?,?,'2026-10-10')`, 2+i, fmt.Sprintf("team %d", i), fmt.Sprintf("2026-10-%02dT00:00:00Z", 12+i))
		projectionExec(t, d, `INSERT INTO pages (id,kind,slug,title,live,parent_id,first_published_at,created_at,updated_at) VALUES (?,'article',?,?,1,900,?,'2026-10-10','2026-10-10'); INSERT INTO articles (page_id,category_id,author_id) VALUES (?,2,1)`, 200+i, fmt.Sprintf("notice-%d", i), fmt.Sprintf("notice %d", i), fmt.Sprintf("2090-10-%02dT00:00:00Z", i+1), 200+i)
	}
	projectionExec(t, d, `INSERT INTO teams (id,name,disbanded_at,created_at,updated_at) VALUES (100,'disbanded','2026-10-10','2099-01-01','2099-01-01'); INSERT INTO home_pins VALUES (107,4),(108,5),(112,6)`)
	out, err := svc.HomePage(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if len(out.Scrims) != 5 || out.Scrims[0].ID != 1 || out.Scrims[4].ID != 13 {
		t.Fatalf("scrim limits=%+v", out.Scrims)
	}
	if len(out.Teams) != 6 || out.Teams[0].ID != 8 || out.Teams[5].ID != 3 || out.Stats.TeamCount != 8 {
		t.Fatalf("team limits=%+v stats=%+v", out.Teams, out.Stats)
	}
	if len(out.Notices) != 5 || out.Notices[0].ID != 206 || out.Notices[4].ID != 202 {
		t.Fatalf("notice limits=%+v", out.Notices)
	}
	if len(out.News) != 4 || out.News[0].ID != 101 || out.News[1].ID != 109 || out.News[2].ID != 107 || out.News[3].ID != 206 {
		t.Fatalf("news limits=%+v", out.News)
	}
	seen := map[int64]bool{}
	pinned := 0
	for _, item := range out.News {
		if seen[item.ID] {
			t.Fatal("duplicate news")
		}
		seen[item.ID] = true
		if item.Pinned {
			pinned++
		}
	}
	if pinned != 3 {
		t.Fatalf("pinned=%d", pinned)
	}
}

func TestHomeFeatureTiePreference(t *testing.T) {
	d, svc, ctx := homeFixture(t)
	projectionExec(t, d, `UPDATE tournaments SET status='draft';
 INSERT INTO tournaments (id,title,status,starts_at,registration_opens_at,registration_closes_at,created_at,updated_at) VALUES
 (90,'earlier registration, later start','published','2026-10-25T00:00:00Z','2026-10-01T00:00:00Z','2026-10-15T00:00:00Z','2026-10-10','2026-10-10'),
 (91,'later registration, earlier start','published','2026-10-20T00:00:00Z','2026-10-02T00:00:00Z','2026-10-15T00:00:00Z','2026-10-10','2026-10-10');`)
	for range 2 {
		out, err := svc.HomePage(ctx)
		if err != nil || out.FeatureTournament == nil || out.FeatureTournament.ID != 91 {
			t.Fatalf("tie=%+v err=%v", out, err)
		}
		projectionExec(t, d, "UPDATE tournaments SET registration_opens_at='2026-10-02T00:00:00Z' WHERE id=90")
	}
}
