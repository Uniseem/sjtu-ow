package comments

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

func TestCommentEditedAtContract(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	insertTestUser(t, d, 1, "member@example.test", "成员")
	setupTestArticle(t, d, 20, true, true)
	svc := NewService(NewStore(d))
	member := newTestCtx(ctx, 1, false)
	mod := newTestCtx(ctx, 1, true)
	root, err := svc.CreateComment(member, CreateCommentInput{ArticleID: 20, Content: "初稿"})
	if err != nil {
		t.Fatal(err)
	}
	reply, err := svc.CreateComment(member, CreateCommentInput{ArticleID: 20, ParentID: &root.ID, Content: "回复"})
	if err != nil {
		t.Fatal(err)
	}
	reg := &api.Registry{}
	NewModule(svc).Routes(reg)
	handler := reg.Handler(func(*http.Request) *app.Viewer { return mod.Viewer })
	read := func() map[string]any {
		t.Helper()
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/articles/20/comments", nil))
		if rec.Code != 200 {
			t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
		}
		var out struct {
			Comments []map[string]any `json:"comments"`
		}
		if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
			t.Fatal(err)
		}
		if len(out.Comments) != 1 {
			t.Fatalf("comments=%v", out.Comments)
		}
		return out.Comments[0]
	}
	assertTime := func(row map[string]any, want *time.Time) {
		t.Helper()
		got, ok := row["edited_at"]
		if !ok {
			t.Fatal("missing edited_at")
		}
		if want == nil {
			if got != nil {
				t.Fatalf("unedited=%v", got)
			}
			return
		}
		text, ok := got.(string)
		if !ok {
			t.Fatalf("edited_at=%v", got)
		}
		parsed, err := time.Parse(time.RFC3339Nano, text)
		if err != nil || !parsed.Equal(*want) {
			t.Fatalf("edited_at=%v want=%v err=%v", got, want, err)
		}
	}
	assertTime(read(), nil)
	if root.EditedAt != nil {
		t.Fatal("create must not mark edited")
	}
	same, err := svc.EditComment(member, root.ID, EditCommentInput{Content: "  初稿  "})
	if err != nil || same.EditedAt != nil || same.Version != root.Version {
		t.Fatalf("unchanged edit=%+v err=%v", same, err)
	}
	// 管理动作更新 updated_at，但不制造 edited_at。
	if err := svc.SetPinned(mod, 20, root.ID, true); err != nil {
		t.Fatal(err)
	}
	if err := svc.SetHidden(mod, root.ID, true); err != nil {
		t.Fatal(err)
	}
	if err := svc.SetHidden(mod, root.ID, false); err != nil {
		t.Fatal(err)
	}
	if _, _, err := svc.ToggleLike(member, root.ID); err != nil {
		t.Fatal(err)
	}
	assertTime(read(), nil)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPatch, fmt.Sprintf("/api/comments/%d", root.ID), bytes.NewBufferString(`{"content":"修订"}`))
	req.Header.Set("Content-Type", "application/json")
	handler.ServeHTTP(rec, req)
	if rec.Code != 200 {
		t.Fatalf("patch status=%d body=%s", rec.Code, rec.Body.String())
	}
	var patch PatchCommentOut
	if err := json.Unmarshal(rec.Body.Bytes(), &patch); err != nil {
		t.Fatal(err)
	}
	edited := patch.Comment
	if edited == nil {
		t.Fatal("missing patch comment")
	}
	if edited.EditedAt == nil || edited.EditedAt.Before(edited.CreatedAt) || !edited.EditedAt.Equal(edited.UpdatedAt) {
		t.Fatalf("edit=%+v", edited)
	}
	assertTime(read(), edited.EditedAt)
	same, err = svc.EditComment(member, root.ID, EditCommentInput{Content: "修订"})
	if err != nil || same.EditedAt == nil || !same.EditedAt.Equal(*edited.EditedAt) || same.Version != edited.Version {
		t.Fatalf("unchanged revision=%+v err=%v", same, err)
	}
	reply, err = svc.EditComment(member, reply.ID, EditCommentInput{Content: "回复修订"})
	if err != nil {
		t.Fatal(err)
	}
	if reply.EditedAt == nil {
		t.Fatal("reply missing edit timestamp")
	}
	replies := read()["replies"].([]any)
	assertTime(replies[0].(map[string]any), reply.EditedAt)
	if err := svc.SetHidden(mod, root.ID, true); err != nil {
		t.Fatal(err)
	}
	if err := svc.SetHidden(mod, root.ID, false); err != nil {
		t.Fatal(err)
	}
	if err := svc.SetPinned(mod, 20, root.ID, true); err != nil {
		t.Fatal(err)
	}
	if _, _, err := svc.ToggleLike(member, root.ID); err != nil {
		t.Fatal(err)
	}
	assertTime(read(), edited.EditedAt)
	if err := svc.DeleteComment(member, root.ID); err != nil {
		t.Fatal(err)
	}
	assertTime(read(), edited.EditedAt)
}
