package accounts

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
)

func deletionPrivacyFixture(t *testing.T) (*db.DB, *Service, *User, *app.Ctx, *dummyMedia) {
	t.Helper()
	d, svc, _, owner, ctx := personalPatchFixture(t)
	dm := &dummyMedia{d: d}
	svc.SetMedia(dm)
	execAll(t, d,
		`INSERT INTO images(id,title,file_name,file_size,width,height,created_at,version) VALUES(7,'旧头像','old.webp',100,100,100,'2026-01-01',1),(9,'新头像','new.webp',100,100,100,'2026-01-01',1),(11,'默认图库','default.webp',100,100,100,'2026-01-01',1)`,
		`INSERT INTO avatar_submissions(user_id,image_id,status,created_at) VALUES(`+itoa(owner.ID)+`,7,'approved','2026-01-01'),(`+itoa(owner.ID)+`,9,'approved','2026-01-02')`,
		`UPDATE users SET avatar_image_id=9 WHERE id=`+itoa(owner.ID),
	)
	if err := d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		if _, err := tx.ExecContext(c, `INSERT INTO email_codes(purpose,email_norm,code_hash,created_at,expires_at) VALUES('password_reset',?,'hash','2026-01-01','2099-01-01')`, owner.EmailNorm); err != nil {
			return err
		}
		_, err := tx.ExecContext(c, `INSERT INTO account_code_flows(token_hash,purpose,email_norm,created_at,expires_at) VALUES('deletion-flow','password_reset',?,'2026-01-01','2099-01-01')`, owner.EmailNorm)
		return err
	}); err != nil {
		t.Fatal(err)
	}
	if err := d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		for _, kind := range []string{"nickname", "motto", "article", "comment"} {
			if _, err := tx.ExecContext(c, `INSERT INTO moderation_items(target_type,target_id,field,excerpt,full_text,text_hash,author_id,created_at) VALUES(?,?,'text','旧文本','旧个人文本',?,?,'2026-01-01')`, kind, owner.ID, kind, owner.ID); err != nil {
				return err
			}
		}
		_, err := tx.ExecContext(c, `INSERT INTO moderation_items(target_type,target_id,field,excerpt,text_hash,created_at) VALUES('nickname',?,'text','其他人昵称','foreign-nickname','2026-01-01')`, owner.ID+999)
		return err
	}); err != nil {
		t.Fatal(err)
	}
	old := outbox.Open(owner.ID)
	if err := d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		_, err := outbox.Send(c, tx, old, svc.siteURL, mail.Letter{Subject: "以前未确认的信", Lead: "不能在注销后发送"}, []mail.Person{{Address: "old-recipient@example.test", Name: "旧收件人"}}, ctx.Now())
		return err
	}); err != nil {
		t.Fatal(err)
	}
	return d, svc, owner, ctx, dm
}

func TestDeletionRemovesUploadedImagesAndOldHeldLettersKeepsCurrentBatch(t *testing.T) {
	d, svc, owner, ctx, dm := deletionPrivacyFixture(t)
	ctx.Letters = outbox.Open(owner.ID)
	if err := d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		_, err := outbox.Send(c, tx, ctx.Letters, svc.siteURL, mail.Letter{Subject: "这次操作的退队通知", Lead: "应当代发一次"}, []mail.Person{{Address: "current-recipient@example.test", Name: "现队长"}}, ctx.Now())
		return err
	}); err != nil {
		t.Fatal(err)
	}
	if _, err := svc.DeleteAccount(ctx, DeleteAccountInput{Password: "Password123!@#"}); err != nil {
		t.Fatal(err)
	}
	if countOf(t, d, `SELECT COUNT(*) FROM images WHERE id IN(7,9)`) != 0 || countOf(t, d, `SELECT COUNT(*) FROM images WHERE id=11`) != 1 || countOf(t, d, `SELECT COUNT(*) FROM avatar_submissions WHERE user_id=?`, owner.ID) != 0 || countOf(t, d, `SELECT COUNT(*) FROM users WHERE id=? AND avatar_image_id IS NOT NULL`, owner.ID) != 0 {
		t.Fatal("uploaded avatar identity remained or default-pool image was removed")
	}
	if countOf(t, d, `SELECT COUNT(*) FROM email_codes WHERE email_norm=?`, owner.EmailNorm) != 0 || countOf(t, d, `SELECT COUNT(*) FROM account_code_flows WHERE email_norm=?`, owner.EmailNorm) != 0 {
		t.Fatal("old code or anonymous email flow survived deletion")
	}
	if countOf(t, d, `SELECT COUNT(*) FROM moderation_items WHERE target_type IN('nickname','motto') AND target_id=?`, owner.ID) != 0 || countOf(t, d, `SELECT COUNT(*) FROM moderation_items WHERE target_type IN('article','comment') AND target_id=?`, owner.ID) != 2 || countOf(t, d, `SELECT COUNT(*) FROM moderation_items WHERE target_type='nickname' AND target_id=?`, owner.ID+999) != 1 {
		t.Fatal("personal profile copies remain or unrelated article review was deleted")
	}
	if len(dm.deleted) != 2 || !ctx.ShouldClearSessionCookie() {
		t.Fatal("physical avatars or session cookie were retained")
	}
	if countOf(t, d, `SELECT COUNT(*) FROM held_letters WHERE actor_id=?`, owner.ID) != 1 || countOf(t, d, `SELECT COUNT(*) FROM held_letters WHERE batch=? AND state='waiting'`, ctx.Letters.Key) != 1 {
		t.Fatal("old held letter retained or current operation letter removed")
	}
	for i := 0; i < 2; i++ {
		if err := d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
			_, _, err := outbox.SendAll(c, tx, ctx.Letters.Key, svc.siteURL, ctx.Now())
			return err
		}); err != nil {
			t.Fatal(err)
		}
	}
	if countOf(t, d, `SELECT COUNT(*) FROM jobs WHERE kind='mail.letter'`) != 1 {
		t.Fatal("system decision enqueued mail more than once")
	}
}

func TestDeletionHTTPAutomaticallySendsOnlyCurrentOperationLetters(t *testing.T) {
	d, svc, owner, ownerCtx, _ := deletionPrivacyFixture(t)
	registry := &api.Registry{}
	api.Post(registry, "/api/test/delete", api.Member, func(ctx *app.Ctx, _ struct{}) (*DeleteAccountResult, error) {
		if err := d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
			_, err := outbox.Send(c, tx, ctx.Letters, svc.siteURL, mail.Letter{Subject: "本次退队通知", Lead: "自动代发"}, []mail.Person{{Address: "captain@example.test", Name: "队长"}}, ctx.Now())
			return err
		}); err != nil {
			return nil, err
		}
		return svc.DeleteAccount(ctx, DeleteAccountInput{Password: "Password123!@#"})
	}, api.NoLimit("isolated deletion settlement test"))
	handler := registry.Handler(func(*http.Request) *app.Viewer { return ownerCtx.Viewer }, api.WithLetters(d, svc.siteURL))
	request := httptest.NewRequest("POST", "/api/test/delete", strings.NewReader(`{}`))
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != 200 || strings.Contains(response.Body.String(), `"letters"`) {
		t.Fatalf("deleted actor was sent to confirmation page: %d %s", response.Code, response.Body.String())
	}
	if countOf(t, d, `SELECT COUNT(*) FROM jobs WHERE kind='mail.letter'`) != 1 || countOf(t, d, `SELECT COUNT(*) FROM held_letters WHERE actor_id=? AND state='waiting'`, owner.ID) != 0 {
		t.Fatal("old mail survived or current operation was not automatically sent")
	}
}

func TestDeletionFailureRollsBackAvatarAndHeldLetterCleanup(t *testing.T) {
	d, svc, owner, ctx, dm := deletionPrivacyFixture(t)
	execAll(t, d, `CREATE TRIGGER fail_avatar_deletion BEFORE DELETE ON avatar_submissions BEGIN SELECT RAISE(ABORT,'test deletion failure'); END`)
	if _, err := svc.DeleteAccount(ctx, DeleteAccountInput{Password: "Password123!@#"}); err == nil || !strings.Contains(err.Error(), "test deletion failure") {
		t.Fatalf("expected avatar failure, got %v", err)
	}
	if countOf(t, d, `SELECT COUNT(*) FROM images WHERE id IN(7,9)`) != 2 || countOf(t, d, `SELECT COUNT(*) FROM avatar_submissions WHERE user_id=?`, owner.ID) != 2 || countOf(t, d, `SELECT COUNT(*) FROM users WHERE id=? AND is_active=1 AND avatar_image_id=9`, owner.ID) != 1 || countOf(t, d, `SELECT COUNT(*) FROM held_letters WHERE actor_id=?`, owner.ID) != 1 || len(dm.deleted) != 0 || ctx.ShouldClearSessionCookie() {
		t.Fatal("failed deletion left partial anonymity, deletion or mail cleanup")
	}
}

func TestDeletionPreservesCompletedAdhocSnapshotsAndLeavesOngoingTeams(t *testing.T) {
	d, svc, _, owner, ctx := personalPatchFixture(t)
	states := []string{"draft", "published", "finished", "cancelled"}
	if err := d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		for i, state := range states {
			id := int64(100 + i)
			if _, err := tx.ExecContext(c, `INSERT INTO tournaments(id,title,status,registration_mode,created_at,updated_at) VALUES(?,'历史赛事',?,'individual','2026-01-01','2026-01-01')`, id, state); err != nil {
				return err
			}
			if _, err := tx.ExecContext(c, `INSERT INTO registrations(id,tournament_id,status,team_name,submitted_at,created_at,updated_at) VALUES(?,?,'approved','历史临时队','2026-01-01','2026-01-01','2026-01-01')`, id, id); err != nil {
				return err
			}
			if _, err := tx.ExecContext(c, `INSERT INTO registration_members(registration_id,tournament_id,user_id,nickname,battletag,is_active) VALUES(?,?,?,'冻结昵称','Frozen#1234',1)`, id, id, owner.ID); err != nil {
				return err
			}
			if _, err := tx.ExecContext(c, `INSERT INTO individual_signups(tournament_id,user_id,registration_id,role_tank,created_at,updated_at) VALUES(?,?,?,1,'2026-01-01','2026-01-01')`, id, owner.ID, id); err != nil {
				return err
			}
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if _, err := svc.DeleteAccount(ctx, DeleteAccountInput{Password: "Password123!@#"}); err != nil {
		t.Fatal(err)
	}
	for i, state := range states {
		id := int64(100 + i)
		if state == "draft" || state == "published" {
			if countOf(t, d, `SELECT COUNT(*) FROM registration_members WHERE registration_id=?`, id) != 0 || countOf(t, d, `SELECT COUNT(*) FROM registrations WHERE id=? AND status='withdrawn'`, id) != 1 {
				t.Fatalf("ongoing %s team was not left", state)
			}
		} else {
			if countOf(t, d, `SELECT COUNT(*) FROM registration_members WHERE registration_id=? AND nickname='冻结昵称' AND battletag='Frozen#1234'`, id) != 1 || countOf(t, d, `SELECT COUNT(*) FROM registrations WHERE id=? AND status='approved' AND roster_version=1`, id) != 1 {
				t.Fatalf("completed %s frozen snapshot changed", state)
			}
		}
	}
	if countOf(t, d, `SELECT COUNT(*) FROM individual_signups WHERE user_id=?`, owner.ID) != 0 {
		t.Fatal("own individual signups survived deletion")
	}
}
