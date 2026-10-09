package tournaments

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	_ "modernc.org/sqlite"
)

func (e *env) handler() http.Handler {
	reg := &api.Registry{}
	NewModule(e.svc).Routes(reg)
	return reg.Handler(func(r *http.Request) *app.Viewer {
		id, _ := strconv.ParseInt(r.Header.Get("X-Test-User"), 10, 64)
		if id == 0 {
			return nil
		}
		v := &app.Viewer{ID: id, EmailVerified: true}
		if r.Header.Get("X-Test-Mgr") == "1" {
			v.Caps = map[app.Cap]struct{}{accounts.CapTournamentsManage: {}}
		}
		return v
	})
}

func (e *env) call(h http.Handler, method, path string, user int64, mgr bool, body string) (int, map[string]any) {
	e.t.Helper()
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	if body != "" {
		req.Header.Set("Content-Type", "application/json")
	}
	if user > 0 {
		req.Header.Set("X-Test-User", strconv.FormatInt(user, 10))
	}
	if mgr {
		req.Header.Set("X-Test-Mgr", "1")
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	var out map[string]any
	_ = json.Unmarshal(rec.Body.Bytes(), &out)
	return rec.Code, out
}

// 接口的门：公开读、登录写、后台要赛事管理能力
func TestRoutesAndGates(t *testing.T) {
	e := newEnv(t)
	h := e.handler()
	a, b, mgr := e.user("队长"), e.user("队员"), e.user("管理")
	tid := e.tour()
	team := e.team("接口队", a, b)
	tp := "/api/tournaments/" + strconv.FormatInt(tid, 10)

	if code, out := e.call(h, "GET", "/api/tournaments", 0, false, ""); code != 200 || len(out["groups"].([]any)) != 4 {
		t.Fatalf("列表：%d %v", code, out)
	}
	if code, out := e.call(h, "GET", tp, a, false, ""); code != 200 {
		t.Fatalf("详情：%d %v", code, out)
	} else if cts := out["viewer"].(map[string]any)["captain_teams"].([]any); len(cts) != 1 {
		t.Fatalf("队长要看到可报名的战队：%v", out["viewer"])
	}
	if code, _ := e.call(h, "GET", "/api/tournaments/abc", 0, false, ""); code != 404 {
		t.Fatalf("坏编号：%d", code)
	}
	// 报名
	body := `{"team_id":` + strconv.FormatInt(team, 10) + `}`
	if code, _ := e.call(h, "POST", tp+"/registrations", 0, false, body); code != 401 {
		t.Fatalf("未登录：%d", code)
	}
	code, out := e.call(h, "POST", tp+"/registrations", a, false, body)
	if code != 200 {
		t.Fatalf("报名：%d %v", code, out)
	}
	rid := int64(out["registration"].(map[string]any)["id"].(float64))
	rp := "/api/registrations/" + strconv.FormatInt(rid, 10)
	if code, _ := e.call(h, "GET", rp, e.user("路人"), false, ""); code != 404 {
		t.Fatalf("路人看不到：%d", code)
	}
	if code, _ := e.call(h, "GET", rp, b, false, ""); code != 200 {
		t.Fatalf("队员看得到：%d", code)
	}
	// 后台
	if code, _ := e.call(h, "GET", "/api/admin/tournaments", a, false, ""); code != 403 {
		t.Fatalf("没有能力：%d", code)
	}
	if code, _ := e.call(h, "GET", "/api/admin/tournaments", 0, false, ""); code != 401 {
		t.Fatalf("没登录：%d", code)
	}
	if code, out := e.call(h, "GET", "/api/admin/tournaments/"+strconv.FormatInt(tid, 10)+"/registrations", mgr, true, ""); code != 200 || len(out["registrations"].([]any)) != 1 {
		t.Fatalf("审核页：%d %v", code, out)
	}
	if code, _ := e.call(h, "POST", "/api/admin/registrations/"+strconv.FormatInt(rid, 10)+"/reject", mgr, true, `{"note":"不行"}`); code != 200 {
		t.Fatalf("驳回：%d", code)
	}
	if code, out := e.call(h, "POST", "/api/admin/tournaments", mgr, true, ""); code != 200 {
		t.Fatalf("新建草稿：%d %v", code, out)
	} else {
		nid := int64(out["tournament"].(map[string]any)["id"].(float64))
		path := "/api/admin/tournaments/" + strconv.FormatInt(nid, 10)
		if code, out := e.call(h, "PATCH", path, mgr, true, `{"base_version":1,"changes":{"title":"新赛事"}}`); code != 200 || out["version"].(float64) != 2 {
			t.Fatalf("自动保存：%d %v", code, out)
		}
		if code, _ := e.call(h, "PATCH", path, mgr, true, `{"base_version":1,"changes":{"title":"又改"}}`); code != 409 {
			t.Fatalf("落后版本：%d", code)
		}
		if code, _ := e.call(h, "POST", path+"/publish", mgr, true, ""); code != 409 {
			t.Fatalf("没填好不能发布：%d", code)
		}
		if code, _ := e.call(h, "DELETE", path, mgr, true, ""); code != 200 {
			t.Fatalf("删草稿：%d", code)
		}
	}
}

// 导入器：编号沿用、可重复跑、指向不存在行的引用置空
func TestImportLegacyTournaments(t *testing.T) {
	e := newEnv(t)
	a, b := e.user("甲"), e.user("乙")
	team := e.team("导入队", a, b)
	legacy, err := sql.Open("sqlite", "file:"+filepath.Join(t.TempDir(), "legacy.sqlite3"))
	if err != nil {
		t.Fatal(err)
	}
	defer legacy.Close()
	for _, s := range []string{
		`CREATE TABLE tournaments_tournament (id INTEGER, title TEXT, summary TEXT, description TEXT, description_plain TEXT, cover_id INTEGER,
			starts_at TEXT, registration_opens_at TEXT, registration_closes_at TEXT, roster_min INTEGER, roster_max INTEGER, sjtu_only INTEGER,
			registration_mode TEXT, auto_approve INTEGER, status TEXT, created_by_id INTEGER, published_at TEXT, reminder_sent_at TEXT,
			moved_from TEXT, participant_contact TEXT, created_at TEXT, updated_at TEXT)`,
		`INSERT INTO tournaments_tournament VALUES (11, '老赛事', '简', '说明', '说明', 777, '2026-06-01 12:00:00', '2026-05-01 00:00:00',
			'2026-05-20 00:00:00', 2, 3, 1, 'team', 0, 'finished', 999, '2026-05-01 00:00:00', NULL, NULL, 'QQ 1', '2026-04-01 00:00:00', '2026-06-02 00:00:00')`,
		`CREATE TABLE tournaments_registration (id INTEGER, tournament_id INTEGER, team_id INTEGER, status TEXT, team_name TEXT,
			roster_version INTEGER, submitted_by_id INTEGER, submitted_at TEXT, status_note TEXT, created_at TEXT, updated_at TEXT)`,
		`INSERT INTO tournaments_registration VALUES (4, 11, ` + strconv.FormatInt(team, 10) + `, 'approved', '导入队', 2, ` + strconv.FormatInt(a, 10) + `, '2026-05-02 00:00:00', '', '2026-05-02 00:00:00', '2026-05-03 00:00:00')`,
		`CREATE TABLE tournaments_registrationmember (id INTEGER, registration_id INTEGER, tournament_id INTEGER, user_id INTEGER, game_account_id INTEGER,
			nickname TEXT, battletag TEXT, is_sjtu INTEGER, rank_tank INTEGER, rank_damage INTEGER, rank_support INTEGER, is_captain INTEGER, is_active INTEGER)`,
		`INSERT INTO tournaments_registrationmember VALUES (8, 4, 11, ` + strconv.FormatInt(a, 10) + `, 424242, '甲', 'Old#1', 1, 2000, NULL, NULL, 1, 1)`,
		`CREATE TABLE tournaments_registrationstatuslog (id INTEGER, registration_id INTEGER, action TEXT, from_status TEXT, to_status TEXT,
			actor_type TEXT, actor_user_id INTEGER, roster_version INTEGER, roster_snapshot TEXT, note TEXT, created_at TEXT)`,
		`INSERT INTO tournaments_registrationstatuslog VALUES (2, 4, 'submit', '', 'pending', 'captain', ` + strconv.FormatInt(a, 10) + `, 1, '[{"nickname":"甲"}]', '', '2026-05-02 00:00:00')`,
		`CREATE TABLE tournaments_individualsignup (id INTEGER, tournament_id INTEGER, user_id INTEGER, game_account_id INTEGER, role_tank INTEGER,
			role_damage INTEGER, role_support INTEGER, registration_id INTEGER, created_at TEXT, updated_at TEXT)`,
		`INSERT INTO tournaments_individualsignup VALUES (6, 11, ` + strconv.FormatInt(b, 10) + `, NULL, 1, 0, 1, NULL, '2026-05-03 00:00:00', '2026-05-03 00:00:00')`,
	} {
		if _, err := legacy.Exec(s); err != nil {
			t.Fatalf("%s: %v", s, err)
		}
	}
	for i := 0; i < 2; i++ {
		if err := ImportLegacyTournaments(e.mgr().Context, e.d, legacy); err != nil {
			t.Fatalf("第 %d 次导入：%v", i+1, err)
		}
	}
	tt, err := GetTournament(e.mgr().Context, e.d.ReadPool(), 11)
	if err != nil || tt == nil || tt.Title != "老赛事" || tt.CoverImageID != nil || tt.CreatedBy != nil || tt.Status != StatusFinished || !tt.SjtuOnly {
		t.Fatalf("赛事 11：%+v %v", tt, err)
	}
	if tt.StartsAt == nil || tt.StartsAt.Format("2006-01-02T15:04:05Z") != "2026-06-01T12:00:00Z" {
		t.Fatalf("时间按 UTC 沿用：%v", tt.StartsAt)
	}
	if e.count(`SELECT COUNT(*) FROM registrations WHERE id = 4 AND roster_version = 2`) != 1 ||
		e.count(`SELECT COUNT(*) FROM registration_members WHERE id = 8 AND game_account_id IS NULL AND battletag = 'Old#1'`) != 1 ||
		e.count(`SELECT COUNT(*) FROM registration_status_logs`) != 1 || e.count(`SELECT COUNT(*) FROM individual_signups WHERE id = 6`) != 1 {
		t.Fatal("报名、名单、日志、个人报名没原样导入")
	}
	// 新建的赛事编号接在导入的后面
	d := e.draft()
	if d.ID <= 11 {
		t.Fatalf("新编号应大于导入的最大编号：%d", d.ID)
	}
}
