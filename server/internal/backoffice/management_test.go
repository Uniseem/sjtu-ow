package backoffice

import (
	"context"
	"encoding/csv"
	"errors"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/tournaments"
)

type managementEnv struct {
	t   *testing.T
	d   *db.DB
	svc *Service
	ctx *app.Ctx
}

func managementFixture(t *testing.T) *managementEnv {
	t.Helper()
	database, err := db.Open(filepath.Join(t.TempDir(), "admin.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { database.Close() })
	if err := db.Migrate(context.Background(), database); err != nil {
		t.Fatal(err)
	}
	now := time.Date(2026, 10, 11, 12, 0, 0, 0, time.UTC)
	service := NewService(database, &api.Registry{})
	service.SetTournamentService(tournaments.NewService(database, "https://example.test"))
	env := &managementEnv{t: t, d: database, svc: service, ctx: &app.Ctx{Context: context.Background(), Clock: clock.Fixed(now), Viewer: &app.Viewer{ID: 1, Nickname: "站长", Superuser: true}}}
	env.exec(`INSERT INTO users(id,email,email_norm,password_hash,nickname,is_sjtu,agreed_terms_at,agreed_cross_border_at,email_verified_at,is_active,is_superuser,show_rank,created_at,updated_at) VALUES(1,'admin@example.test','admin@example.test','h','站长',1,?,?,?,1,1,0,?,?)`, stamp(now), stamp(now), stamp(now), stamp(now), stamp(now))
	env.exec(`INSERT INTO users(id,email,email_norm,password_hash,nickname,is_sjtu,agreed_terms_at,agreed_cross_border_at,email_verified_at,is_active,is_superuser,show_rank,created_at,updated_at) VALUES(2,'player@example.test','player@example.test','h','队员',1,?,?,?,1,0,0,?,?)`, stamp(now), stamp(now), stamp(now), stamp(now), stamp(now))
	env.exec(`INSERT INTO user_roles(user_id,role,created_at) VALUES(2,'tournament_admin',?)`, stamp(now))
	return env
}
func stamp(value time.Time) string { return db.FormatUTC(value) }
func (env *managementEnv) exec(query string, args ...any) {
	env.t.Helper()
	if err := env.d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error { _, err := tx.ExecContext(ctx, query, args...); return err }); err != nil {
		env.t.Fatalf("query %s: %v", query, err)
	}
}
func (env *managementEnv) count(query string, args ...any) int {
	env.t.Helper()
	var count int
	if err := env.d.ReadPool().QueryRow(query, args...).Scan(&count); err != nil {
		env.t.Fatal(err)
	}
	return count
}
func managementStatus(t *testing.T, err error, want int) {
	t.Helper()
	var problem *api.Error
	if !errors.As(err, &problem) || problem.Status != want {
		t.Fatalf("error=%v want=%d", err, want)
	}
}
func (env *managementEnv) event(id int64, status string) {
	env.t.Helper()
	now := env.ctx.Now()
	env.exec(`INSERT INTO tournaments(id,title,status,registration_mode,starts_at,registration_opens_at,registration_closes_at,created_by,created_at,updated_at) VALUES(?,?,?,'team',?,?,?,?,?,?)`, id, "赛事", status, stamp(now.Add(48*time.Hour)), stamp(now.Add(-time.Hour)), stamp(now.Add(24*time.Hour)), 1, stamp(now), stamp(now))
}
func (env *managementEnv) registration(id, event int64, status string) {
	env.t.Helper()
	now := stamp(env.ctx.Now())
	env.exec(`INSERT INTO registrations(id,tournament_id,team_name,status,submitted_by,submitted_at,created_at,updated_at) VALUES(?,?,?, ?,2,?,?,?)`, id, event, "=危险队名", status, now, now, now)
	env.exec(`INSERT INTO registration_members(registration_id,tournament_id,user_id,nickname,battletag,is_sjtu,is_captain,is_active) VALUES(?,?,2,'=昵称','@game#123',1,1,1)`, id, event)
}

func TestUserPatchOnlyOwnsTwoFieldsAndInvalidSiblingRemainsUnchanged(t *testing.T) {
	env := managementFixture(t)
	nickname := "新昵称"
	sjtu := false
	receipt, err := env.svc.patchUser(env.ctx, PatchUserIn{ID: 2, BaseVersion: 1, Changes: UserChanges{Nickname: &nickname, IsSJTU: &sjtu}})
	if err != nil {
		t.Fatal(err)
	}
	if receipt.Version != 2 || len(receipt.Saved) != 2 {
		t.Fatalf("receipt=%+v", receipt)
	}
	var rank, active int
	var email string
	if err := env.d.ReadPool().QueryRow(`SELECT show_rank,is_active,email FROM users WHERE id=2`).Scan(&rank, &active, &email); err != nil {
		t.Fatal(err)
	}
	if rank != 0 || active != 1 || email != "player@example.test" {
		t.Fatal("patch touched fields outside the user form")
	}
	blank := ""
	sjtu = true
	partial, err := env.svc.patchUser(env.ctx, PatchUserIn{ID: 2, BaseVersion: 2, Changes: UserChanges{Nickname: &blank, IsSJTU: &sjtu}})
	if err != nil {
		t.Fatal(err)
	}
	if len(partial.Fields["nickname"]) == 0 || len(partial.Saved) != 1 || partial.Saved[0] != "is_sjtu" {
		t.Fatalf("partial=%+v", partial)
	}
	var actual string
	if err := env.d.ReadPool().QueryRow(`SELECT nickname FROM users WHERE id=2`).Scan(&actual); err != nil {
		t.Fatal(err)
	}
	if actual != nickname {
		t.Fatal("invalid nickname replaced saved nickname")
	}
}
func TestUserPatchConflictDoesNotOverwriteAndReturnsCurrentProjection(t *testing.T) {
	env := managementFixture(t)
	env.exec(`UPDATE users SET version=8,nickname='另一个编辑' WHERE id=2`)
	nickname := "我的草稿"
	_, err := env.svc.patchUser(env.ctx, PatchUserIn{ID: 2, BaseVersion: 1, Changes: UserChanges{Nickname: &nickname}})
	managementStatus(t, err, 409)
	var actual string
	if err := env.d.ReadPool().QueryRow(`SELECT nickname FROM users WHERE id=2`).Scan(&actual); err != nil {
		t.Fatal(err)
	}
	if actual != "另一个编辑" {
		t.Fatal("stale write overwrote current value")
	}
	var problem *api.Error
	if !errors.As(err, &problem) || problem.Current == nil {
		t.Fatal("stale error omitted current values")
	}
}
func TestSingleUserRuleCannotDeleteOrReplaceUnrelatedRule(t *testing.T) {
	env := managementFixture(t)
	first, err := env.svc.addUserRule(env.ctx, AddUserRuleIn{ID: 2, Feature: "article_comment", Allowed: false, Note: "请先联系管理员"})
	if err != nil {
		t.Fatal(err)
	}
	if len(first.Rules) != 1 || first.Rules[0].Allowed || first.Rules[0].Note != "请先联系管理员" {
		t.Fatalf("rule=%+v", first)
	}
	second, err := env.svc.addUserRule(env.ctx, AddUserRuleIn{ID: 2, Feature: "article_submit", Allowed: true, Note: "保留的说明"})
	if err != nil {
		t.Fatal(err)
	}
	if len(second.Rules) != 2 {
		t.Fatal("adding a rule replaced another rule")
	}
	if _, err := env.svc.addUserRule(env.ctx, AddUserRuleIn{ID: 2, Feature: "article_comment", Allowed: true, Note: "覆盖"}); err == nil {
		t.Fatal("duplicate single rule silently overwrote")
	}
	result, err := env.svc.deleteUserRule(env.ctx, RuleIDIn{ID: 2, Rule: api.ID(featureID("article_comment"))})
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Rules) != 1 || result.Rules[0].Feature != "article_submit" || result.Rules[0].Note != "保留的说明" {
		t.Fatalf("delete damaged sibling rule: %+v", result)
	}
	if env.count(`SELECT COUNT(*) FROM audit_log WHERE object_type='user' AND object_id=2`) != 3 {
		t.Fatal("rule mutations did not leave audit trail")
	}
}
func TestRoleRestrictionCountsRespectExplicitUserAllow(t *testing.T) {
	env := managementFixture(t)
	roles, err := env.svc.addRestriction(env.ctx, AddRestrictionIn{ID: 3, Feature: "article_submit", Note: "组限制"})
	if err != nil {
		t.Fatal(err)
	}
	var contributor RoleGroup
	for _, role := range roles.Groups {
		if role.Name == accounts.RoleContributor {
			contributor = role
		}
	}
	if contributor.People != 1 {
		t.Fatalf("restricted member counted as contributor; people=%d", contributor.People)
	}
	if _, err := env.svc.addUserRule(env.ctx, AddUserRuleIn{ID: 2, Feature: "article_submit", Allowed: true, Note: "本人单独允许"}); err != nil {
		t.Fatal(err)
	}
	roles, err = env.svc.roles(env.ctx, struct{}{})
	if err != nil {
		t.Fatal(err)
	}
	for _, role := range roles.Groups {
		if role.Name == accounts.RoleContributor && role.People != 2 {
			t.Fatalf("explicit allow did not override restriction: %+v", role)
		}
	}
	if _, err := env.svc.addRestriction(env.ctx, AddRestrictionIn{ID: 3, Feature: "article_submit"}); err == nil {
		t.Fatal("duplicate role restriction accepted")
	}
	if _, err := env.svc.deleteRestriction(env.ctx, RuleIDIn{ID: 4, Rule: api.ID(featureID("article_submit"))}); err == nil {
		t.Fatal("wrong role removed another role restriction")
	}
	if env.count(`SELECT COUNT(*) FROM feature_role_restrictions WHERE role='tournament_admin'`) != 1 {
		t.Fatal("role restriction lost")
	}
}
func TestManualRoleIDsRemainStableAsNewRolesAreDiscovered(t *testing.T) {
	env := managementFixture(t)
	env.exec(`INSERT INTO user_roles(user_id,role,created_at) VALUES(2,'组织组',?)`, stamp(env.ctx.Now()))
	before, err := knownRoles(env.ctx.Context, env.d.ReadPool())
	if err != nil {
		t.Fatal(err)
	}
	var original int64
	for _, role := range before {
		if role.Name == "组织组" {
			original = role.ID
		}
	}
	env.exec(`INSERT INTO user_roles(user_id,role,created_at) VALUES(2,'AAA新组',?)`, stamp(env.ctx.Now()))
	resolved, err := roleByID(env.ctx.Context, env.d.ReadPool(), original)
	if err != nil {
		t.Fatal(err)
	}
	if resolved.Name != "组织组" {
		t.Fatalf("stable role id changed meaning: %+v", resolved)
	}
}
func TestUserSearchFiltersBeforePaginationAndHandlesLiteralWildcards(t *testing.T) {
	env := managementFixture(t)
	env.exec(`UPDATE users SET nickname='百分%成员' WHERE id=2`)
	found, err := env.svc.searchUsers(env.ctx, UserSearchIn{Query: "%", Role: accounts.RoleTournamentAdmin, Active: "yes", SJTU: "yes"})
	if err != nil {
		t.Fatal(err)
	}
	if found.Total != 1 || len(found.Users) != 1 || found.Users[0].ID != 2 {
		t.Fatalf("filters=%+v", found)
	}
	none, err := env.svc.searchUsers(env.ctx, UserSearchIn{Query: "_"})
	if err != nil {
		t.Fatal(err)
	}
	if none.Total != 0 {
		t.Fatal("literal underscore became SQL wildcard")
	}
	if _, err := env.svc.searchUsers(env.ctx, UserSearchIn{Role: "unknown"}); err == nil {
		t.Fatal("unknown role filter accepted")
	}
}
func TestBulkApprovalPartialFailuresKeepActualTransitions(t *testing.T) {
	env := managementFixture(t)
	env.event(1, "published")
	env.event(2, "cancelled")
	env.registration(10, 1, "pending")
	env.registration(11, 2, "pending")
	receipt, err := env.svc.bulkApprove(env.ctx, BulkApproveIn{IDs: []int64{10, 11, 999}})
	if err != nil {
		t.Fatal(err)
	}
	if len(receipt.Approved) != 1 || receipt.Approved[0] != 10 || len(receipt.Failed) != 2 {
		t.Fatalf("receipt=%+v", receipt)
	}
	if env.count(`SELECT COUNT(*) FROM registrations WHERE id=10 AND status='approved'`) != 1 {
		t.Fatal("approved receipt had no real transition")
	}
	if env.count(`SELECT COUNT(*) FROM registrations WHERE id=11 AND status='pending'`) != 1 {
		t.Fatal("cancelled event's registration was changed")
	}
	if env.count(`SELECT COUNT(*) FROM registration_status_logs WHERE registration_id=10 AND action='approve'`) != 1 {
		t.Fatal("original approval side effect was skipped")
	}
	if _, err := env.svc.bulkApprove(env.ctx, BulkApproveIn{IDs: []int64{10, 10}}); err == nil {
		t.Fatal("duplicate batch ids accepted")
	}
}
func TestRegistrationCSVMatchesLegacyFieldsProtectsFormulasAndAudits(t *testing.T) {
	env := managementFixture(t)
	env.event(1, "published")
	env.registration(10, 1, "pending")
	env.exec(`INSERT INTO contacts(user_id,type,value,created_at,updated_at) VALUES(2,'qq','=123',?,?)`, stamp(env.ctx.Now()), stamp(env.ctx.Now()))
	result, err := env.svc.exportRegistrations(env.ctx, RegistrationQuery{TournamentID: 1, Status: "pending"})
	if err != nil {
		t.Fatal(err)
	}
	records, err := csv.NewReader(strings.NewReader(strings.TrimPrefix(result.CSV, "\ufeff"))).ReadAll()
	if err != nil {
		t.Fatal(err)
	}
	if len(records) != 2 || len(records[0]) != 10 || records[0][0] != "赛事" || records[0][9] != "联系方式" {
		t.Fatalf("CSV=%v", records)
	}
	if records[1][1] != "'=危险队名" || records[1][5] != "'=昵称" || records[1][6] != "'@game#123" {
		t.Fatalf("formula escaping=%v", records[1])
	}
	if !strings.Contains(records[1][9], "QQ =123") {
		t.Fatalf("authorized contact missing: %v", records[1])
	}
	if env.count(`SELECT COUNT(*) FROM audit_log WHERE action='registration.export' AND object_type='tournament' AND object_id=1`) != 1 {
		t.Fatal("CSV did not record audit event")
	}
	manager := *env.ctx
	manager.Viewer = &app.Viewer{ID: 2, Caps: map[app.Cap]struct{}{accounts.CapTournamentsManage: {}}}
	restricted, err := env.svc.exportRegistrations(&manager, RegistrationQuery{TournamentID: 1})
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(restricted.CSV, "联系方式") || strings.Contains(restricted.CSV, "=123") {
		t.Fatal("CSV leaked contacts to viewer without contacts cap")
	}
}
func TestHomeReadsRealWorkerTableProjectsTodosAndRestrictsSetup(t *testing.T) {
	env := managementFixture(t)
	env.event(1, "published")
	env.registration(10, 1, "pending")
	now := stamp(env.ctx.Now())
	env.exec(`INSERT INTO worker_status(id,started_at,heartbeat_at) VALUES(1,?,?)`, now, now)
	env.svc.SetBackupStatusReader(func(context.Context, time.Time) ([]string, error) {
		return []string{"最近一次备份已经超过36小时"}, nil
	})
	page, err := env.svc.Home(env.ctx)
	if err != nil {
		t.Fatal(err)
	}
	pending, backup := false, false
	for _, todo := range page.Todo {
		if todo.URL == "/admin/registrations/?status=pending" && todo.Count == 1 {
			pending = true
		}
		if strings.Contains(todo.Text, "备份已经") {
			backup = true
		}
		if strings.Contains(todo.Text, "worker）没在运行") {
			t.Fatal("fresh real worker heartbeat reported offline")
		}
	}
	if !pending || !backup || page.Setup == nil {
		t.Fatalf("home=%+v", page)
	}
	env.exec(`UPDATE worker_status SET heartbeat_at=? WHERE id=1`, stamp(env.ctx.Now().Add(-3*time.Minute)))
	stale, err := env.svc.Home(env.ctx)
	if err != nil {
		t.Fatal(err)
	}
	offline := false
	for _, todo := range stale.Todo {
		if strings.Contains(todo.Text, "worker）没在运行") {
			offline = true
		}
	}
	if !offline {
		t.Fatal("stale worker heartbeat not surfaced")
	}
	normal := *env.ctx
	normal.Viewer = &app.Viewer{ID: 2, Nickname: "赛事管理员", Caps: map[app.Cap]struct{}{accounts.CapAdminEnter: {}, accounts.CapTournamentsManage: {}}}
	ordinary, err := env.svc.Home(&normal)
	if err != nil {
		t.Fatal(err)
	}
	if ordinary.Setup != nil {
		t.Fatal("non-superuser received setup checks")
	}
	for _, todo := range ordinary.Todo {
		if strings.Contains(todo.Text, "备份已经") {
			t.Fatal("non-superuser received backup information")
		}
	}
}
func TestBackofficeRoutesGateBeforeDatabaseOrBodyMutation(t *testing.T) {
	registry := &api.Registry{}
	NewModule(NewService(nil, registry)).Routes(registry)
	for _, route := range registry.Routes() {
		if route.Pattern == "/api/admin/navigation" {
			continue
		}
		target := strings.ReplaceAll(strings.ReplaceAll(route.Pattern, "{id}", "1"), "{rule}", "1")
		for _, viewer := range []*app.Viewer{nil, {ID: 2}} {
			handler := registry.Handler(func(*http.Request) *app.Viewer { return viewer })
			request := httptest.NewRequest(route.Method, target, strings.NewReader(`{}`))
			request.Header.Set("Content-Type", "application/json")
			recorder := httptest.NewRecorder()
			handler.ServeHTTP(recorder, request)
			expected := 403
			if viewer == nil {
				expected = 401
			}
			if recorder.Code != expected {
				t.Fatalf("%s %s=%d expected=%d body=%s", route.Method, target, recorder.Code, expected, recorder.Body.String())
			}
		}
	}
}
