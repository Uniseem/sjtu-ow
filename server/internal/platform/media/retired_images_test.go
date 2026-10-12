package media

import (
	"context"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestBusinessRetirementDoesNotRelaxLibraryDelete(t *testing.T) {
	module, database, ctx := round290Media(t)
	ctx.Viewer = &app.Viewer{ID: 1, Caps: map[app.Cap]struct{}{"admin.enter": {}, "images.contribute": {}}}
	err := database.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, `INSERT INTO images(id,collection_id,title,file_name,file_size,width,height,uploader_id,created_at) VALUES
   (100,5,'Retired logo','logo.webp',1,10,10,1,'2026-10-10'),
   (101,5,'Used logo','used.webp',1,10,10,1,'2026-10-10'),
   (102,3,'Retired avatar','avatar.webp',1,10,10,1,'2026-10-10'),
   (103,3,'Current avatar','current.webp',1,10,10,1,'2026-10-10'),
   (104,3,'No owned submission','other.webp',1,10,10,1,'2026-10-10'),
   (105,4,'Submission image','submission.webp',1,10,10,1,'2026-10-10');
   INSERT INTO avatar_submissions(user_id,image_id,status,created_at) VALUES(1,102,'approved','2026-10-10'),(1,103,'approved','2026-10-10');
   UPDATE users SET avatar_image_id=103 WHERE id=1;
   INSERT INTO teams(id,name,logo_image_id,created_at,updated_at) VALUES(1,'Using logo',101,'2026-10-10','2026-10-10');`)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	// Library deletion remains forbidden for both private business collections.
	for _, id := range []int64{100, 102} {
		mediaRound290Status(t, module.svc.DeleteImage(ctx, id), 403)
	}
	if err := module.svc.RetireUnusedTeamLogo(ctx, 100); err != nil {
		t.Fatal(err)
	}
	if err := module.svc.RetireUnusedUserAvatar(ctx, 102); err != nil {
		t.Fatal(err)
	}
	// A business call cannot delete an in-use image, another kind of image or a
	// private avatar for which the caller has no submission history.
	for _, id := range []int64{101, 103, 104, 105} {
		if err := module.svc.RetireUnusedTeamLogo(ctx, id); err != nil {
			t.Fatal(err)
		}
		if err := module.svc.RetireUnusedUserAvatar(ctx, id); err != nil {
			t.Fatal(err)
		}
	}
	var count int
	if err := database.ReadPool().QueryRowContext(ctx.Context, "SELECT COUNT(*) FROM images WHERE id IN(100,102)").Scan(&count); err != nil || count != 0 {
		t.Fatalf("retired records count=%d err=%v", count, err)
	}
	if err := database.ReadPool().QueryRowContext(ctx.Context, "SELECT COUNT(*) FROM images WHERE id IN(101,103,104,105)").Scan(&count); err != nil || count != 4 {
		t.Fatalf("protected records count=%d err=%v", count, err)
	}
}
