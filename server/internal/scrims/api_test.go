package scrims

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
			v.Caps = map[app.Cap]struct{}{accounts.CapScrimsManage: {}}
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

// 接口的门：公开读、登录写、后台要内战管理能力
func TestRoutesAndGates(t *testing.T) {
	e := newEnv(t)
	h := e.handler()
	u := e.user("甲", 2000, 2000, 2000)
	sid := e.scrim()
	sp := "/api/scrims/" + strconv.FormatInt(sid, 10)
	if code, out := e.call(h, "GET", "/api/scrims", 0, false, ""); code != 200 || len(out["scrims"].([]any)) != 1 {
		t.Fatalf("列表：%d %v", code, out)
	}
	if code, _ := e.call(h, "GET", sp, 0, false, ""); code != 200 {
		t.Fatalf("详情：%d", code)
	}
	if code, _ := e.call(h, "GET", "/api/scrims/abc", 0, false, ""); code != 404 {
		t.Fatalf("坏编号：%d", code)
	}
	body := `{"game_account_id":` + strconv.FormatInt(e.account(u), 10) + `,"roles":["tank"]}`
	if code, _ := e.call(h, "POST", sp+"/signup", 0, false, body); code != 401 {
		t.Fatalf("未登录：%d", code)
	}
	if code, out := e.call(h, "POST", sp+"/signup", u, false, body); code != 200 {
		t.Fatalf("报名：%d %v", code, out)
	}
	if code, out := e.call(h, "GET", sp, u, false, ""); code != 200 || out["mine"] == nil {
		t.Fatalf("详情带我的报名：%d %v", code, out)
	}
	if code, _ := e.call(h, "DELETE", sp+"/signup", u, false, ""); code != 200 {
		t.Fatalf("取消：%d", code)
	}
	if code, _ := e.call(h, "GET", "/api/admin/scrims", u, false, ""); code != 403 {
		t.Fatalf("没有能力：%d", code)
	}
	if code, out := e.call(h, "POST", "/api/admin/scrims", 900, true, ""); code != 200 {
		t.Fatalf("新建草稿：%d %v", code, out)
	} else {
		nid := int64(out["scrim"].(map[string]any)["id"].(float64))
		ap := "/api/admin/scrims/" + strconv.FormatInt(nid, 10)
		if code, out := e.call(h, "PATCH", ap, 900, true, `{"base_version":1,"changes":{"title":"新内战"}}`); code != 200 || out["version"].(float64) != 2 {
			t.Fatalf("自动保存：%d %v", code, out)
		}
		if code, _ := e.call(h, "PATCH", ap, 900, true, `{"base_version":1,"changes":{"title":"又改"}}`); code != 409 {
			t.Fatalf("落后版本：%d", code)
		}
		if code, _ := e.call(h, "POST", ap+"/publish", 900, true, ""); code != 409 {
			t.Fatalf("没填好不能发布：%d", code)
		}
		if code, _ := e.call(h, "GET", ap+"/board", 900, true, ""); code != 200 {
			t.Fatalf("分队页：%d", code)
		}
		if code, _ := e.call(h, "DELETE", ap, 900, true, ""); code != 200 {
			t.Fatalf("删草稿：%d", code)
		}
	}
}

// 导入器：编号沿用、可重复跑、指向不存在行的引用置空
func TestImportLegacyScrims(t *testing.T) {
	e := newEnv(t)
	u := e.user("甲", 2000, 2000, 2000)
	legacy, err := sql.Open("sqlite", "file:"+filepath.Join(t.TempDir(), "legacy.sqlite3"))
	if err != nil {
		t.Fatal(err)
	}
	defer legacy.Close()
	for _, s := range []string{
		`CREATE TABLE core_sitesettings (id INTEGER, qq_group_url TEXT)`,
		`INSERT INTO core_sitesettings VALUES (1, 'https://qm.qq.com/abc')`,
		`CREATE TABLE scrims_scrim (id INTEGER, title TEXT, description TEXT, description_plain TEXT, starts_at TEXT, signup_closes_at TEXT,
			format TEXT, sjtu_only INTEGER, status TEXT, teams_generated_at TEXT, roster_changed_at TEXT, reminder_sent_at TEXT,
			moved_from TEXT, created_by_id INTEGER, created_at TEXT, updated_at TEXT)`,
		`INSERT INTO scrims_scrim VALUES (21, '老内战', 'x', 'x', '2026-06-05 12:00:00', NULL, 'open_6v6', 1, 'finished', '2026-06-05 11:00:00', NULL, NULL, NULL, 999, '2026-06-01 00:00:00', '2026-06-06 00:00:00')`,
		`CREATE TABLE scrims_scrimsignup (id INTEGER, scrim_id INTEGER, user_id INTEGER, game_account_id INTEGER, role_tank INTEGER, role_damage INTEGER,
			role_support INTEGER, is_selected INTEGER, team TEXT, assigned_role TEXT, rating_used INTEGER, created_at TEXT, updated_at TEXT)`,
		`INSERT INTO scrims_scrimsignup VALUES (7, 21, ` + strconv.FormatInt(u, 10) + `, 424242, 1, 0, 1, 1, 'a', '', 3100, '2026-06-02 00:00:00', '2026-06-02 00:00:00')`,
	} {
		if _, err := legacy.Exec(s); err != nil {
			t.Fatalf("%s: %v", s, err)
		}
	}
	for i := 0; i < 2; i++ {
		if err := ImportLegacyScrims(e.mgr().Context, e.d, legacy); err != nil {
			t.Fatalf("第 %d 次导入：%v", i+1, err)
		}
	}
	sc := e.get(21)
	if sc.Title != "老内战" || sc.Format != Open6 || sc.CreatedBy != nil || sc.Status != StatusFinished || sc.TeamsGeneratedAt == nil {
		t.Fatalf("内战 21：%+v", sc)
	}
	if e.count(`SELECT COUNT(*) FROM scrim_signups WHERE id = 7 AND team = 'a' AND rating_used = 3100 AND game_account_id IS NULL`) != 1 {
		t.Fatal("报名没原样导入")
	}
	var group string
	e.d.ReadPool().QueryRow(`SELECT qq_group_url FROM site_settings WHERE id = 1`).Scan(&group)
	if group != "https://qm.qq.com/abc" {
		t.Fatalf("社团 QQ 群链接要带过来：%q", group)
	}
	if d := e.draft(); d.ID <= 21 {
		t.Fatalf("新编号应大于导入的最大编号：%d", d.ID)
	}
}
