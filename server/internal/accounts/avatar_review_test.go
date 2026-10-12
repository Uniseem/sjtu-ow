package accounts

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
)

func avatarReviewStatus(t *testing.T, err error, want int) {
	t.Helper()
	var problem *api.Error
	if !errors.As(err, &problem) || problem.Status != want {
		t.Fatalf("error=%v want=%d", err, want)
	}
}

func TestAvatarReviewDeletesCurrentImageAndFreezesOwnerNotification(t *testing.T) {
	svc, dm, d := newAvatarTestEnv(t)
	ctx := &app.Ctx{Context: context.Background(), Viewer: &app.Viewer{ID: 1, Superuser: true}, Letters: outbox.Open(1)}
	if err := d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		if _, err := tx.ExecContext(c, `INSERT INTO images(id,title,file_name,file_size,width,height,created_at,version) VALUES(7,'头像','face.webp',100,100,100,'2026-01-01',1)`); err != nil {
			return err
		}
		if _, err := tx.ExecContext(c, `INSERT INTO avatar_submissions(id,user_id,image_id,status,created_at) VALUES(8,1,7,'approved','2026-01-01')`); err != nil {
			return err
		}
		_, err := tx.ExecContext(c, `UPDATE users SET avatar_image_id=7 WHERE id=1`)
		return err
	}); err != nil {
		t.Fatal(err)
	}
	if err := svc.ReviewAvatar(ctx, 8, "porn", "请换一张图片"); err != nil {
		t.Fatal(err)
	}
	var imageCount, userImageCount, held, jobs int
	for query, target := range map[string]*int{
		`SELECT COUNT(*) FROM images WHERE id=7`:                                 &imageCount,
		`SELECT COUNT(*) FROM users WHERE avatar_image_id=7`:                     &userImageCount,
		`SELECT COUNT(*) FROM held_letters WHERE actor_id=1 AND state='waiting'`: &held,
		`SELECT COUNT(*) FROM jobs WHERE kind='mail.letter'`:                     &jobs,
	} {
		if err := d.ReadPool().QueryRow(query).Scan(target); err != nil {
			t.Fatal(err)
		}
	}
	if imageCount != 0 || userImageCount != 0 || held != 1 || jobs != 0 || len(dm.deleted) != 1 || dm.deleted[0] != 7 {
		t.Fatalf("delete/freeze: image=%d user=%d held=%d jobs=%d files=%v", imageCount, userImageCount, held, jobs, dm.deleted)
	}
	var body, recipients string
	if err := d.ReadPool().QueryRow(`SELECT letter,recipients FROM held_letters WHERE actor_id=1`).Scan(&body, &recipients); err != nil {
		t.Fatal(err)
	}
	var letter mail.Letter
	if err := json.Unmarshal([]byte(body), &letter); err != nil {
		t.Fatal(err)
	}
	if letter.Subject != "你的头像已被撤下" || len(letter.Facts) != 2 || letter.Facts[0] != [2]string{"原因", "色情低俗"} || letter.Facts[1] != [2]string{"说明", "请换一张图片"} || !strings.Contains(recipients, "user@example.com") {
		t.Fatalf("letter=%+v people=%s", letter, recipients)
	}
	items, total, err := svc.ListAvatars(ctx, "taken_down", 1, 24)
	if err != nil {
		t.Fatal(err)
	}
	if total != 1 || len(items) != 1 || items[0].ImageID != nil || items[0].ReviewedBy == nil || *items[0].ReviewedBy != 1 || items[0].ReasonDisplay != "色情低俗" || items[0].Note != "请换一张图片" || items[0].TurnedDown != 1 || items[0].IsCurrent {
		t.Fatalf("projection=%+v total=%d", items, total)
	}
	avatarReviewStatus(t, svc.ReviewAvatar(ctx, 8, "porn", "第二次"), http.StatusConflict)
	if ctx.Letters.Held != 1 || len(dm.deleted) != 1 {
		t.Fatal("repeat decision emitted another letter or deleted again")
	}
}

func TestAvatarReviewValidatesReasonAndCurrentUseBeforeMutation(t *testing.T) {
	svc, _, d := newAvatarTestEnv(t)
	ctx := &app.Ctx{Context: context.Background(), Viewer: &app.Viewer{ID: 1, Superuser: true}, Letters: outbox.Open(1)}
	if err := d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, `INSERT INTO avatar_submissions(id,user_id,status,created_at) VALUES(8,1,'approved','2026-01-01')`)
		return err
	}); err != nil {
		t.Fatal(err)
	}
	avatarReviewStatus(t, svc.ReviewAvatar(ctx, 8, "", ""), 422)
	avatarReviewStatus(t, svc.ReviewAvatar(ctx, 8, "porn", strings.Repeat("字", 201)), 422)
	avatarReviewStatus(t, svc.ReviewAvatar(ctx, 8, "porn", ""), 409)
	var state string
	if err := d.ReadPool().QueryRow(`SELECT status FROM avatar_submissions WHERE id=8`).Scan(&state); err != nil {
		t.Fatal(err)
	}
	if state != "approved" || ctx.Letters.Held != 0 {
		t.Fatal("invalid decision mutated status or mail")
	}
	ctx.Viewer = &app.Viewer{ID: 1, Caps: map[app.Cap]struct{}{CapTournamentsManage: {}}}
	avatarReviewStatus(t, svc.ReviewAvatar(ctx, 999, "porn", ""), 403)
	ctx.Viewer = &app.Viewer{ID: 1, Superuser: true, Disabled: true}
	avatarReviewStatus(t, svc.ReviewAvatar(ctx, 999, "porn", ""), 403)
}

func TestAvatarReviewCannotRetireReplacedUpload(t *testing.T) {
	svc, dm, d := newAvatarTestEnv(t)
	ctx := &app.Ctx{Context: context.Background(), Viewer: &app.Viewer{ID: 1, Superuser: true}, Letters: outbox.Open(1)}
	if err := d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		for _, id := range []int64{7, 9} {
			if _, err := tx.ExecContext(c, `INSERT INTO images(id,title,file_name,file_size,width,height,created_at,version) VALUES(?,'头像','face.webp',100,100,100,'2026-01-01',1)`, id); err != nil {
				return err
			}
		}
		if _, err := tx.ExecContext(c, `INSERT INTO avatar_submissions(id,user_id,image_id,status,created_at) VALUES(8,1,7,'approved','2026-01-01')`); err != nil {
			return err
		}
		_, err := tx.ExecContext(c, `UPDATE users SET avatar_image_id=9 WHERE id=1`)
		return err
	}); err != nil {
		t.Fatal(err)
	}
	avatarReviewStatus(t, svc.ReviewAvatar(ctx, 8, "porn", ""), 409)
	var current, images int
	if err := d.ReadPool().QueryRow(`SELECT avatar_image_id FROM users WHERE id=1`).Scan(&current); err != nil {
		t.Fatal(err)
	}
	if err := d.ReadPool().QueryRow(`SELECT COUNT(*) FROM images WHERE id IN(7,9)`).Scan(&images); err != nil {
		t.Fatal(err)
	}
	if current != 9 || images != 2 || ctx.Letters.Held != 0 || len(dm.deleted) != 0 {
		t.Fatal("replaced-upload decision affected current avatar, files or letters")
	}
}

func TestAvatarReviewNotificationFailureRollsBackRetirement(t *testing.T) {
	svc, dm, d := newAvatarTestEnv(t)
	ctx := &app.Ctx{Context: context.Background(), Viewer: &app.Viewer{ID: 1, Superuser: true}, Letters: outbox.Open(1)}
	if err := d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		queries := []string{
			`INSERT INTO images(id,title,file_name,file_size,width,height,created_at,version) VALUES(7,'头像','face.webp',100,100,100,'2026-01-01',1)`,
			`INSERT INTO avatar_submissions(id,user_id,image_id,status,created_at) VALUES(8,1,7,'approved','2026-01-01')`,
			`UPDATE users SET avatar_image_id=7 WHERE id=1`,
			`CREATE TRIGGER reject_avatar_letter BEFORE INSERT ON held_letters BEGIN SELECT RAISE(ABORT,'test letter failure'); END`,
		}
		for _, query := range queries {
			if _, err := tx.ExecContext(c, query); err != nil {
				return err
			}
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if err := svc.ReviewAvatar(ctx, 8, "porn", ""); err == nil {
		t.Fatal("failed notification reported success")
	}
	var image, current int
	var status string
	if err := d.ReadPool().QueryRow(`SELECT COUNT(*) FROM images WHERE id=7`).Scan(&image); err != nil {
		t.Fatal(err)
	}
	if err := d.ReadPool().QueryRow(`SELECT avatar_image_id FROM users WHERE id=1`).Scan(&current); err != nil {
		t.Fatal(err)
	}
	if err := d.ReadPool().QueryRow(`SELECT status FROM avatar_submissions WHERE id=8`).Scan(&status); err != nil {
		t.Fatal(err)
	}
	if image != 1 || current != 7 || status != "approved" || len(dm.deleted) != 0 || ctx.Letters.Held != 0 {
		t.Fatal("failed notification left partial avatar retirement")
	}
}
