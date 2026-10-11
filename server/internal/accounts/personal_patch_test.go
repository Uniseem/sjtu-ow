package accounts

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type personalPatchClock struct {
	now  time.Time
	hook func()
}

func (c *personalPatchClock) Now() time.Time {
	if c.hook != nil {
		hook := c.hook
		c.hook = nil
		hook()
	}
	return c.now
}

func personalPatchFixture(t *testing.T) (*db.DB, *Service, *personalPatchClock, *User, *app.Ctx) {
	t.Helper()
	database := newTestDB(t)
	clock := &personalPatchClock{now: time.Date(2026, 10, 11, 8, 0, 0, 0, time.UTC)}
	sessions := auth.NewStore(database, clock)
	service := NewService(database, clock, "https://example.invalid", sessions, nil)
	owner := newVerifiedUser(t, database, "personal-owner@example.invalid", "Owner", "Password123!@#", true)
	token, err := sessions.Create(context.Background(), owner.ID)
	if err != nil {
		t.Fatal(err)
	}
	return database, service, clock, owner, newTestCtx(context.Background(), owner, token, false)
}

func personalPatchStatus(t *testing.T, err error, status int) *api.Error {
	t.Helper()
	var result *api.Error
	if !errors.As(err, &result) || result.Status != status {
		t.Fatalf("error=%v want status=%d", err, status)
	}
	return result
}

func personalPatchHandler(service *Service, viewer **app.Viewer) http.Handler {
	registry := &api.Registry{}
	NewModule(service).Routes(registry)
	return registry.Handler(func(*http.Request) *app.Viewer { return *viewer })
}

func personalPatchRequest(t *testing.T, handler http.Handler, path, body string, status int) *httptest.ResponseRecorder {
	t.Helper()
	request := httptest.NewRequest(http.MethodPatch, path, strings.NewReader(body))
	request.Header.Set("Content-Type", "application/json")
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, request)
	if recorder.Code != status {
		t.Fatalf("PATCH %s: %d want=%d body=%s", path, recorder.Code, status, recorder.Body.String())
	}
	return recorder
}

func TestPersonalProfilePatchExplicitFalseDoesNotClearOmittedFields(t *testing.T) {
	database, service, _, owner, ctx := personalPatchFixture(t)
	err := database.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, "UPDATE users SET show_rank=1,motto='Keep motto',main_role='tank',flex_roles='damage,support' WHERE id=?", owner.ID)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	viewer := ctx.Viewer
	handler := personalPatchHandler(service, &viewer)
	recorder := personalPatchRequest(t, handler, "/api/me/profile", `{"base_version":1,"changes":{"is_sjtu":false,"show_rank":false}}`, http.StatusOK)
	var saved UpdateProfileResult
	if err := json.Unmarshal(recorder.Body.Bytes(), &saved); err != nil {
		t.Fatal(err)
	}
	if saved.Values == nil || saved.Values.IsSJTU || saved.Values.ShowRank || saved.Version != 2 {
		t.Fatalf("false selections lost: %+v", saved)
	}
	current, err := service.Store().GetByID(ctx.Context, owner.ID)
	if err != nil {
		t.Fatal(err)
	}
	if current.IsSJTU || current.ShowRank || current.Nickname != "Owner" || current.Motto != "Keep motto" || current.MainRole != "tank" || current.FlexRoles != "damage,support" {
		t.Fatalf("patch cleared unrelated fields: %+v", profileValues(current))
	}
	recorder = personalPatchRequest(t, handler, "/api/me/profile", `{"base_version":2,"changes":{"nickname":"Updated"}}`, http.StatusOK)
	if err := json.Unmarshal(recorder.Body.Bytes(), &saved); err != nil {
		t.Fatal(err)
	}
	if saved.Values == nil || saved.Values.IsSJTU || saved.Values.ShowRank || saved.Values.Motto != "Keep motto" {
		t.Fatalf("omitted false privacy flags changed: %+v", saved.Values)
	}
}

func TestPersonalProfilePositionGroupPartiallySavesIndependentFields(t *testing.T) {
	database, service, _, owner, ctx := personalPatchFixture(t)
	err := database.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, "UPDATE users SET main_role='tank',flex_roles='support',motto='Before' WHERE id=?", owner.ID)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	viewer := ctx.Viewer
	recorder := personalPatchRequest(t, personalPatchHandler(service, &viewer), "/api/me/profile", `{"base_version":1,"changes":{"nickname":"Updated","motto":"After","main_role":"damage","flex_roles":"invalid-role"}}`, http.StatusOK)
	var saved UpdateProfileResult
	if err := json.Unmarshal(recorder.Body.Bytes(), &saved); err != nil {
		t.Fatal(err)
	}
	if len(saved.Fields["flex_roles"]) == 0 || saved.Values == nil || saved.Values.Nickname != "Updated" || saved.Values.Motto != "After" || saved.Values.MainRole != "tank" || saved.Values.FlexRoles != "support" {
		t.Fatalf("position group was not atomic: %+v", saved)
	}
	for _, field := range saved.Saved {
		if field == "main_role" || field == "flex_roles" {
			t.Fatalf("rejected group incorrectly marked saved: %+v", saved)
		}
	}
	current, err := service.Store().GetByID(ctx.Context, owner.ID)
	if err != nil || current.MainRole != "tank" || current.FlexRoles != "support" || current.Nickname != "Updated" {
		t.Fatalf("database partial-save mismatch: %+v %v", current, err)
	}
	// The valid group is canonicalized together, excluding the selected main.
	recorder = personalPatchRequest(t, personalPatchHandler(service, &viewer), "/api/me/profile", fmt.Sprintf(`{"base_version":%d,"changes":{"main_role":"damage","flex_roles":"support,tank,damage,tank"}}`, saved.Version), http.StatusOK)
	if err := json.Unmarshal(recorder.Body.Bytes(), &saved); err != nil {
		t.Fatal(err)
	}
	if saved.Values.MainRole != "damage" || saved.Values.FlexRoles != "tank,support" {
		t.Fatalf("normalization mismatch: %+v", saved.Values)
	}
}

func TestPersonalStaleProfileReturnsOnlySafeEditorValuesAndDoesNotWrite(t *testing.T) {
	_, service, _, owner, ctx := personalPatchFixture(t)
	viewer := ctx.Viewer
	handler := personalPatchHandler(service, &viewer)
	personalPatchRequest(t, handler, "/api/me/profile", `{"base_version":1,"changes":{"nickname":"Latest"}}`, http.StatusOK)
	response := personalPatchRequest(t, handler, "/api/me/profile", `{"base_version":1,"changes":{"nickname":"Stale overwrite"}}`, http.StatusConflict)
	var payload struct {
		Current ProfileCurrent `json:"current"`
	}
	if err := json.Unmarshal(response.Body.Bytes(), &payload); err != nil {
		t.Fatal(err)
	}
	if payload.Current.Version != 2 || payload.Current.Values.Nickname != "Latest" {
		t.Fatalf("stale projection wrong: %s", response.Body.String())
	}
	for _, secret := range []string{"password_hash", "email_verified_at", "session", "personal-owner@example.invalid", "is_superuser"} {
		if strings.Contains(response.Body.String(), secret) {
			t.Fatalf("conflict leaked %q: %s", secret, response.Body.String())
		}
	}
	current, err := service.Store().GetByID(ctx.Context, owner.ID)
	if err != nil || current.Nickname != "Latest" || current.Version != 2 {
		t.Fatalf("stale write changed owner: %+v %v", current, err)
	}
}

func TestPersonalGamePatchNullOmissionAndEqualRanksHaveDifferentSemantics(t *testing.T) {
	_, service, clock, _, ctx := personalPatchFixture(t)
	tank, damage := 10, 20
	game, err := service.AddGameAccount(ctx, AddGameAccountInput{Battletag: "Fixture#1234", RankTank: &tank, RankDamage: &damage})
	if err != nil {
		t.Fatal(err)
	}
	originalDate := game.RanksUpdatedAt
	clock.now = clock.now.Add(24 * time.Hour)
	viewer := ctx.Viewer
	handler := personalPatchHandler(service, &viewer)
	path := fmt.Sprintf("/api/me/game-accounts/%d", game.ID)
	recorder := personalPatchRequest(t, handler, path, fmt.Sprintf(`{"base_version":%d,"changes":{"rank_tank":10}}`, game.Version), http.StatusOK)
	var same GameAccountResult
	if err := json.Unmarshal(recorder.Body.Bytes(), &same); err != nil {
		t.Fatal(err)
	}
	if !same.RanksUpdatedAt.Equal(originalDate) || same.RankDamage == nil || *same.RankDamage != 20 {
		t.Fatalf("equal rank refreshed date or cleared omitted damage: %+v", same)
	}
	recorder = personalPatchRequest(t, handler, path, fmt.Sprintf(`{"base_version":%d,"changes":{"battletag":"Renamed#1234"}}`, same.Version), http.StatusOK)
	var renamed GameAccountResult
	if err := json.Unmarshal(recorder.Body.Bytes(), &renamed); err != nil {
		t.Fatal(err)
	}
	if renamed.RankTank == nil || *renamed.RankTank != 10 || renamed.RankDamage == nil || *renamed.RankDamage != 20 || !renamed.RanksUpdatedAt.Equal(originalDate) {
		t.Fatalf("tag-only patch changed ranks: %+v", renamed)
	}
	recorder = personalPatchRequest(t, handler, path, fmt.Sprintf(`{"base_version":%d,"changes":{"rank_tank":null}}`, renamed.Version), http.StatusOK)
	var cleared GameAccountResult
	if err := json.Unmarshal(recorder.Body.Bytes(), &cleared); err != nil {
		t.Fatal(err)
	}
	if cleared.RankTank != nil || cleared.RankDamage == nil || *cleared.RankDamage != 20 || !cleared.RanksUpdatedAt.Equal(clock.now) {
		t.Fatalf("explicit null not distinguished from omission: %+v", cleared)
	}
	stored, err := service.Store().GetGameAccountByID(ctx.Context, game.ID)
	if err != nil || stored.RankTank != nil || stored.RankDamage == nil || *stored.RankDamage != 20 {
		t.Fatalf("persisted null wrong: %+v %v", stored, err)
	}
}

func TestPersonalGamePatchPartiallySavesValidFieldsAndRejectsUnknownFields(t *testing.T) {
	_, service, _, _, ctx := personalPatchFixture(t)
	rank := 10
	game, err := service.AddGameAccount(ctx, AddGameAccountInput{Battletag: "Partial#1234", RankTank: &rank})
	if err != nil {
		t.Fatal(err)
	}
	viewer := ctx.Viewer
	handler := personalPatchHandler(service, &viewer)
	path := fmt.Sprintf("/api/me/game-accounts/%d", game.ID)
	recorder := personalPatchRequest(t, handler, path, fmt.Sprintf(`{"base_version":%d,"changes":{"battletag":"ValidTag#1234","rank_tank":999}}`, game.Version), http.StatusOK)
	var result GameAccountResult
	if err := json.Unmarshal(recorder.Body.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if result.Battletag != "ValidTag#1234" || result.RankTank == nil || *result.RankTank != 10 || len(result.Fields["rank_tank"]) == 0 {
		t.Fatalf("rank rejection lost valid tag: %+v", result)
	}
	for _, field := range result.Saved {
		if field == "rank_tank" {
			t.Fatalf("invalid rank marked saved: %+v", result)
		}
	}
	personalPatchRequest(t, handler, path, fmt.Sprintf(`{"base_version":%d,"changes":{"user_id":999}}`, result.Version), http.StatusBadRequest)
	current, err := service.Store().GetGameAccountByID(ctx.Context, game.ID)
	if err != nil || current.UserID != ctx.Viewer.ID || current.Battletag != "ValidTag#1234" {
		t.Fatalf("unknown patch field changed game: %+v %v", current, err)
	}
}

func TestPersonalNonOwnerCannotWriteOrObtainStaleGameAndContactValues(t *testing.T) {
	database, service, _, _, ownerCtx := personalPatchFixture(t)
	game, err := service.AddGameAccount(ownerCtx, AddGameAccountInput{Battletag: "SecretOwner#1234"})
	if err != nil {
		t.Fatal(err)
	}
	contact, err := service.AddContact(ownerCtx, AddContactInput{Type: ContactQQ, Value: "123456789"})
	if err != nil {
		t.Fatal(err)
	}
	other := newVerifiedUser(t, database, "personal-other@example.invalid", "Other", "Password123!@#", true)
	otherCtx := newTestCtx(context.Background(), other, "", false)
	for _, superuser := range []bool{false, true} {
		otherCtx.Viewer.Superuser = superuser
		viewer := otherCtx.Viewer
		handler := personalPatchHandler(service, &viewer)
		responses := []*httptest.ResponseRecorder{
			personalPatchRequest(t, handler, fmt.Sprintf("/api/me/game-accounts/%d", game.ID), `{"base_version":0,"changes":{"battletag":"Hijack#1234"}}`, http.StatusNotFound),
			personalPatchRequest(t, handler, fmt.Sprintf("/api/me/contacts/%d", contact.ID), `{"base_version":0,"changes":{"value":"987654321"}}`, http.StatusNotFound),
		}
		for _, response := range responses {
			for _, private := range []string{"SecretOwner", "123456789", `"current"`} {
				if strings.Contains(response.Body.String(), private) {
					t.Fatalf("non-owner received %q: %s", private, response.Body.String())
				}
			}
		}
	}
	stored, err := service.Store().GetGameAccountByID(ownerCtx.Context, game.ID)
	if err != nil || stored.Battletag != "SecretOwner#1234" {
		t.Fatal("non-owner changed game account")
	}
	storedContact, err := service.Store().GetContactByID(ownerCtx.Context, contact.ID)
	if err != nil || storedContact.Value != "123456789" {
		t.Fatal("non-owner changed contact")
	}
}

func TestPersonalContactTypeAndValueAreValidatedAsOneGroup(t *testing.T) {
	_, service, _, _, ctx := personalPatchFixture(t)
	qq, err := service.AddContact(ctx, AddContactInput{Type: ContactQQ, Value: "123456789"})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := service.AddContact(ctx, AddContactInput{Type: ContactWeChat, Value: "sample_wechat"}); err != nil {
		t.Fatal(err)
	}
	viewer := ctx.Viewer
	handler := personalPatchHandler(service, &viewer)
	path := fmt.Sprintf("/api/me/contacts/%d", qq.ID)
	recorder := personalPatchRequest(t, handler, path, fmt.Sprintf(`{"base_version":%d,"changes":{"type":"wechat","value":"new_wechat"}}`, qq.Version), http.StatusOK)
	var duplicate ContactResult
	if err := json.Unmarshal(recorder.Body.Bytes(), &duplicate); err != nil {
		t.Fatal(err)
	}
	if duplicate.Version != qq.Version || len(duplicate.Saved) != 0 || len(duplicate.Fields["type"]) == 0 || duplicate.Type != ContactQQ || duplicate.Value != "123456789" {
		t.Fatalf("duplicate type lost old values: %+v", duplicate)
	}
	recorder = personalPatchRequest(t, handler, path, fmt.Sprintf(`{"base_version":%d,"changes":{"type":"phone","value":"not-a-phone"}}`, qq.Version), http.StatusOK)
	var invalid ContactResult
	if err := json.Unmarshal(recorder.Body.Bytes(), &invalid); err != nil {
		t.Fatal(err)
	}
	if invalid.Type != ContactQQ || invalid.Value != "123456789" || invalid.Version != qq.Version || len(invalid.Fields["value"]) == 0 {
		t.Fatalf("invalid combined value partially wrote: %+v", invalid)
	}
	recorder = personalPatchRequest(t, handler, path, fmt.Sprintf(`{"base_version":%d,"changes":{"type":"phone","value":"13800138000"}}`, qq.Version), http.StatusOK)
	var valid ContactResult
	if err := json.Unmarshal(recorder.Body.Bytes(), &valid); err != nil {
		t.Fatal(err)
	}
	if valid.Type != ContactPhone || valid.Value != "13800138000" || valid.Version != qq.Version+1 || len(valid.Saved) != 2 {
		t.Fatalf("valid pair not saved: %+v", valid)
	}
	stale := personalPatchRequest(t, handler, path, fmt.Sprintf(`{"base_version":%d,"changes":{"value":"13900139000"}}`, qq.Version), http.StatusConflict)
	var current struct {
		Current ContactCurrent `json:"current"`
	}
	if err := json.Unmarshal(stale.Body.Bytes(), &current); err != nil {
		t.Fatal(err)
	}
	if current.Current.Values.Type != ContactPhone || current.Current.Values.Value != "13800138000" || current.Current.Version != valid.Version {
		t.Fatalf("contact conflict current wrong: %s", stale.Body.String())
	}
	stored, err := service.Store().GetContactByID(ctx.Context, qq.ID)
	if err != nil || stored.Value != "13800138000" || stored.Type != ContactPhone {
		t.Fatalf("failed patch lost saved contact: %+v %v", stored, err)
	}
}

func TestPersonalDeleteAccountRechecksCaptainInsideWriteTransaction(t *testing.T) {
	database, service, clock, owner, ctx := personalPatchFixture(t)
	preflight, err := service.GetProfile(ctx)
	if err != nil || len(preflight.DeletionBlockers) != 0 {
		t.Fatalf("fixture has blocker: %+v %v", preflight, err)
	}
	// DeleteAccount calls its clock after the optimistic captain read and before
	// opening its write transaction. Add the captain at that exact boundary.
	fired := false
	var hookErr error
	clock.hook = func() {
		fired = true
		hookErr = database.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
			if _, err := tx.ExecContext(c, "INSERT INTO teams(id,name,created_at,updated_at) VALUES(1000,'New captain team',?,?)", clock.now.Format(time.RFC3339Nano), clock.now.Format(time.RFC3339Nano)); err != nil {
				return err
			}
			_, err := tx.ExecContext(c, "INSERT INTO team_memberships(team_id,user_id,role,joined_at) VALUES(1000,?,'captain',?)", owner.ID, clock.now.Format(time.RFC3339Nano))
			return err
		})
	}
	_, err = service.DeleteAccount(ctx, DeleteAccountInput{Password: "Password123!@#"})
	if hookErr != nil || !fired {
		t.Fatalf("race boundary hook failed: fired=%v err=%v", fired, hookErr)
	}
	personalPatchStatus(t, err, http.StatusBadRequest)
	current, err := service.Store().GetByID(ctx.Context, owner.ID)
	if err != nil || current == nil || !current.IsActive || current.Email != owner.Email {
		t.Fatalf("captain account anonymized: %+v %v", current, err)
	}
	session, err := service.sessions.Lookup(ctx.Context, ctx.SessionToken)
	if err != nil || session == nil {
		t.Fatalf("rejected deletion revoked session: %+v %v", session, err)
	}
	if countOf(t, database, "SELECT COUNT(*) FROM team_memberships WHERE team_id=1000 AND user_id=? AND role='captain'", owner.ID) != 1 {
		t.Fatal("rejected deletion removed captain membership")
	}
}

func TestGameDeletionPreservesUnfinishedActivitySignups(t *testing.T) {
	for _, activity := range []struct{ table, signups, foreign string }{{"scrims", "scrim_signups", "scrim_id"}, {"tournaments", "individual_signups", "tournament_id"}} {
		for _, state := range []string{"draft", "published", "finished", "cancelled"} {
			t.Run(activity.table+"/"+state, func(t *testing.T) {
				database, service, _, owner, ctx := personalPatchFixture(t)
				game, err := service.AddGameAccount(ctx, AddGameAccountInput{Battletag: "DeleteTest#1234"})
				if err != nil {
					t.Fatal(err)
				}
				err = database.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
					if _, err := tx.ExecContext(c, "INSERT INTO "+activity.table+"(id,title,status,created_at,updated_at) VALUES(700,'Activity',?,'2026-10-11T08:00:00Z','2026-10-11T08:00:00Z')", state); err != nil {
						return err
					}
					_, err := tx.ExecContext(c, "INSERT INTO "+activity.signups+"("+activity.foreign+",user_id,game_account_id,role_tank,created_at,updated_at) VALUES(700,?,?,1,'2026-10-11T08:00:00Z','2026-10-11T08:00:00Z')", owner.ID, game.ID)
					return err
				})
				if err != nil {
					t.Fatal(err)
				}
				_, err = service.DeleteGameAccount(ctx, game.ID)
				if state == "draft" || state == "published" {
					personalPatchStatus(t, err, http.StatusBadRequest)
					var count int
					if err := database.ReadPool().QueryRow("SELECT COUNT(*) FROM game_accounts WHERE id=?", game.ID).Scan(&count); err != nil || count != 1 {
						t.Fatal("refused delete lost account")
					}
				} else {
					if err != nil {
						t.Fatal(err)
					}
					var remaining int
					if err := database.ReadPool().QueryRow("SELECT COUNT(*) FROM " + activity.signups + " WHERE game_account_id IS NULL").Scan(&remaining); err != nil || remaining != 1 {
						t.Fatal("completed history was lost instead of unlinked")
					}
				}
			})
		}
	}
}
