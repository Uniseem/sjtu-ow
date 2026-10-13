package content

import (
	"net/http"
	"testing"
)

func TestArticleWriterRolesKeepGuideSeparateFromCommentsAndCategories(t *testing.T) {
	for _, tc := range []struct {
		name      string
		role      string
		superuser bool
		guide     bool
		comments  bool
		author    bool
		schedule  bool
	}{
		{name: "member", guide: true},
		{name: "tournament administrator", role: "tournament_admin", guide: true, comments: true},
		{name: "scrim administrator", role: "scrim_admin", guide: true, comments: true},
		{name: "certified author", role: "certified_author", comments: true, schedule: true},
		{name: "content editor", role: "content_editor", comments: true, author: true, schedule: true},
		{name: "superuser", superuser: true, comments: true, author: true, schedule: true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			m, _, writer, _ := round290Module(t)
			writer.Viewer.Superuser = tc.superuser
			writer.Viewer.Roles = map[string]struct{}{}
			if tc.role != "" {
				writer.Viewer.Roles[tc.role] = struct{}{}
			}
			if tc.author {
				writer.Viewer.Caps[CapArticlesEditAny] = struct{}{}
				writer.Viewer.Caps[CapArticlesEditAuthor] = struct{}{}
			}
			open := &Category{Name: "Open", Slug: "open", AllowSubmission: true}
			closed := &Category{Name: "Closed", Slug: "closed"}
			for _, category := range []*Category{open, closed} {
				if err := m.svc.store.CreateCategory(writer.Context, category); err != nil {
					t.Fatal(err)
				}
			}
			projection, err := m.newArticleEditor(writer, struct{}{})
			if err != nil {
				t.Fatal(err)
			}
			if projection.Guide != tc.guide || projection.Capabilities.EditComments != tc.comments || projection.Capabilities.EditAuthor != tc.author || projection.Capabilities.EditSchedule != tc.schedule {
				t.Fatalf("wrong writer capabilities: %+v guide=%v", projection.Capabilities, projection.Guide)
			}
			wantCategories := 1
			if tc.comments {
				wantCategories = 2
			}
			if len(projection.Categories) != wantCategories {
				t.Fatalf("wrong category choices: %+v", projection.Categories)
			}
			created, err := m.svc.CreateDraft(writer, CreateDraftInput{Title: "Initial closed", CategoryID: &closed.ID, BodyMD: "Body"})
			if tc.comments {
				if err != nil {
					t.Fatalf("staff writer cannot create closed-category draft: %v", err)
				}
			} else {
				round290ErrorStatus(t, err, http.StatusUnprocessableEntity)
				created, err = m.svc.CreateDraft(writer, CreateDraftInput{Title: "Initial open", CategoryID: &open.ID, BodyMD: "Body"})
				if err != nil {
					t.Fatal(err)
				}
			}
			saved, err := m.svc.SaveDraft(writer, created.ID, SaveDraftInput{BaseVersion: created.Version, Changes: map[string]any{
				"category_id": float64(closed.ID), "comments_enabled": false, "author_id": float64(2), "slug": "writer-address",
			}})
			if err != nil {
				t.Fatal(err)
			}
			for field, allowed := range map[string]bool{"category_id": tc.comments, "comments_enabled": tc.comments, "author_id": tc.author, "slug": tc.schedule} {
				if (len(saved.Fields[field]) == 0) != allowed {
					t.Fatalf("%s permission mismatch: %+v", field, saved)
				}
			}
			article, err := m.svc.store.GetArticleByID(writer.Context, created.ID)
			if err != nil {
				t.Fatal(err)
			}
			detail, err := m.editorProjection(writer, article)
			if err != nil {
				t.Fatal(err)
			}
			wantCategory := open.ID
			if tc.comments {
				wantCategory = closed.ID
			}
			if detail.Revision.CategoryID == nil || *detail.Revision.CategoryID != wantCategory || detail.Revision.CommentsEnabled == tc.comments {
				t.Fatalf("real saved category/comment state: %+v", detail.Revision)
			}
			published, err := m.svc.Publish(writer, created.ID, PublishInput{BaseVersion: saved.Version})
			if err != nil || !published.Live || published.CategoryID == nil || *published.CategoryID != wantCategory || published.CommentsEnabled == tc.comments {
				t.Fatalf("real writer publication: %+v %v", published, err)
			}
		})
	}
}
