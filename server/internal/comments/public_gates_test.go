package comments

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func gateExec(t *testing.T, d *db.DB, q string) {
	t.Helper()
	if err := d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error { _, err := tx.ExecContext(ctx, q); return err }); err != nil {
		t.Fatal(err)
	}
}
func gateFixture(t *testing.T) (*db.DB, *Service) {
	t.Helper()
	d := newTestDB(t)
	insertTestUser(t, d, 1, "owner@test.example", "作者")
	insertTestUser(t, d, 2, "member@test.example", "成员")
	setupTestArticle(t, d, 10, true, true)
	gateExec(t, d, `INSERT INTO comments (id,article_id,user_id,content,created_at,updated_at) VALUES (100,10,1,'ORIGINAL','2026-10-10T00:00:00Z','2026-10-10T00:00:00Z'),(101,10,1,'OTHER','2026-10-10T00:00:00Z','2026-10-10T00:00:00Z')`)
	return d, NewService(NewStore(d))
}
func gateSnapshot(t *testing.T, d *db.DB) string {
	t.Helper()
	all := []any{}
	for _, table := range []string{"comments", "comment_likes"} {
		rows, err := d.ReadPool().QueryContext(context.Background(), "SELECT * FROM "+table+" ORDER BY 1,2")
		if err != nil {
			t.Fatal(err)
		}
		cols, err := rows.Columns()
		if err != nil {
			t.Fatal(err)
		}
		data := [][]any{}
		for rows.Next() {
			values := make([]any, len(cols))
			dest := make([]any, len(cols))
			for i := range values {
				dest[i] = &values[i]
			}
			if err := rows.Scan(dest...); err != nil {
				t.Fatal(err)
			}
			data = append(data, values)
		}
		if err := rows.Err(); err != nil {
			t.Fatal(err)
		}
		_ = rows.Close()
		all = append(all, data)
	}
	encoded, err := json.Marshal(all)
	if err != nil {
		t.Fatal(err)
	}
	return string(encoded)
}

func TestPublicCommentHTTPMatrix(t *testing.T) {
	actions := []struct{ name, method, path, body string }{
		{"list", "GET", "/api/articles/10/comments", ""}, {"post", "POST", "/api/articles/10/comments", `{"content":"NEW"}`},
		{"reply", "POST", "/api/articles/10/comments", `{"content":"REPLY","parent_id":100}`},
		{"edit", "PATCH", "/api/comments/100", `{"content":"EDITED"}`}, {"delete", "DELETE", "/api/comments/100", ""},
		{"like", "POST", "/api/comments/100/like", `{}`}, {"hide", "POST", "/api/comments/100/hide", `{"hidden":true}`},
		{"unhide", "POST", "/api/comments/100/hide", `{"hidden":false}`}, {"pin", "POST", "/api/comments/100/pin", `{"article_id":10,"pinned":true}`},
		{"unpin", "POST", "/api/comments/100/pin", `{"article_id":10,"pinned":false}`},
	}
	roles := []struct {
		name string
		v    *app.Viewer
	}{
		{"visitor", nil}, {"member", &app.Viewer{ID: 2}}, {"author", &app.Viewer{ID: 1}},
		{"moderator", &app.Viewer{ID: 1, Caps: map[app.Cap]struct{}{CapCommentsModerate: {}}}},
		{"superuser", &app.Viewer{ID: 1, Superuser: true}}, {"disabled", &app.Viewer{ID: 1, Superuser: true, Disabled: true}},
	}
	states := []string{"UPDATE pages SET live=0 WHERE id=10", "UPDATE pages SET is_public=0 WHERE id=10", "DELETE FROM pages WHERE id=10"}
	for _, state := range states {
		for _, role := range roles {
			for _, action := range actions {
				t.Run(role.name+"/"+action.name+"/"+state, func(t *testing.T) {
					d, svc := gateFixture(t)
					gateExec(t, d, state)
					before := gateSnapshot(t, d)
					reg := &api.Registry{}
					NewModule(svc).Routes(reg)
					req := httptest.NewRequest(action.method, action.path, bytes.NewBufferString(action.body))
					req.Header.Set("Content-Type", "application/json")
					rec := httptest.NewRecorder()
					reg.Handler(func(*http.Request) *app.Viewer { return role.v }).ServeHTTP(rec, req)
					want := 404
					if action.method != "GET" {
						if role.v == nil || role.v.Disabled {
							want = 401
						} else if (action.name == "hide" || action.name == "unhide" || action.name == "pin" || action.name == "unpin") && !role.v.HasCap(CapCommentsModerate) {
							want = 403
						}
					}
					if rec.Code != want {
						t.Fatalf("status=%d want=%d body=%s", rec.Code, want, rec.Body.String())
					}
					if before != gateSnapshot(t, d) {
						t.Fatal("rejected action changed database")
					}
				})
			}
		}
	}
}

func TestCommentStorePublicChecksInsideTransaction(t *testing.T) {
	for _, state := range []string{"UPDATE pages SET live=0 WHERE id=10", "UPDATE pages SET is_public=0 WHERE id=10"} {
		for _, name := range []string{"post", "edit", "delete", "hide", "pin", "unpin", "like"} {
			t.Run(name+state, func(t *testing.T) {
				d, _ := gateFixture(t)
				gateExec(t, d, state)
				before := gateSnapshot(t, d)
				store := NewStore(d)
				ctx := context.Background()
				var err error
				switch name {
				case "post":
					id := int64(1)
					err = store.CreateComment(ctx, &Comment{ArticleID: 10, UserID: &id, Content: "NEW"})
				case "edit":
					err = store.UpdateCommentContent(ctx, 100, "NEW", 1)
				case "delete":
					err = store.SoftDeleteComment(ctx, 100, 1)
				case "hide":
					err = store.SetCommentHidden(ctx, 100, true)
				case "pin":
					err = store.SetCommentPinned(ctx, 10, 100, true)
				case "unpin":
					err = store.SetCommentPinned(ctx, 10, 100, false)
				case "like":
					_, _, err = store.ToggleLike(ctx, 100, 1)
				}
				if err == nil {
					t.Fatal("transaction gate bypassed")
				}
				if before != gateSnapshot(t, d) {
					t.Fatal("failed transaction changed database")
				}
			})
		}
	}
}

func TestClosedCommentsAndUnpinIsolation(t *testing.T) {
	d, svc := gateFixture(t)
	ctx := newTestCtx(context.Background(), 1, true)
	if err := svc.SetPinned(ctx, 10, 100, true); err != nil {
		t.Fatal(err)
	}
	if err := svc.SetPinned(ctx, 10, 101, false); err != nil {
		t.Fatal(err)
	}
	pinned, err := svc.store.GetCommentByID(ctx.Context, 100)
	if err != nil || !pinned.IsPinned {
		t.Fatal("unpin of another comment cleared the pin")
	}
	before := gateSnapshot(t, d)
	if err := svc.SetPinned(ctx, 999, 100, false); err == nil || before != gateSnapshot(t, d) {
		t.Fatal("wrong article unpin accepted")
	}
	gateExec(t, d, "UPDATE articles SET comments_enabled=0 WHERE page_id=10")
	if _, err := svc.ListComments(ctx, 10, ListCommentsInput{}); err != nil {
		t.Fatal(err)
	}
	if _, err := svc.CreateComment(ctx, CreateCommentInput{ArticleID: 10, Content: "NEW"}); err == nil {
		t.Fatal("closed post accepted")
	}
	if _, err := svc.EditComment(ctx, 100, EditCommentInput{Content: "NEW"}); err == nil {
		t.Fatal("closed edit accepted")
	}
	if _, _, err := svc.ToggleLike(ctx, 100); err != nil {
		t.Fatal(err)
	}
	if err := svc.SetHidden(ctx, 100, true); err != nil {
		t.Fatal(err)
	}
	if err := svc.SetHidden(ctx, 100, false); err != nil {
		t.Fatal(err)
	}
	if err := svc.DeleteComment(ctx, 100); err != nil {
		t.Fatal(err)
	}
}

func TestReplyParentCheckedInsideTransaction(t *testing.T) {
	for _, state := range []string{"UPDATE comments SET is_hidden=1 WHERE id=100", "UPDATE comments SET is_deleted=1 WHERE id=100", "UPDATE comments SET article_id=11 WHERE id=100"} {
		d, _ := gateFixture(t)
		gateExec(t, d, `INSERT INTO pages (id,kind,slug,title,live,created_at,updated_at) VALUES (11,'article','other-article','other',1,'2026-10-10','2026-10-10'); INSERT INTO articles (page_id) VALUES (11)`)
		gateExec(t, d, state)
		before := gateSnapshot(t, d)
		id, parent := int64(1), int64(100)
		if err := NewStore(d).CreateComment(context.Background(), &Comment{ArticleID: 10, UserID: &id, ParentID: &parent, Content: "REPLY"}); err == nil {
			t.Fatal("invalid reply parent accepted")
		}
		if before != gateSnapshot(t, d) {
			t.Fatal("invalid reply modified database")
		}
	}
}
