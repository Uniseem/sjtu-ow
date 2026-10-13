package content

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestAdminArticleStateRequiresApprovedScheduleAndKeepsRevisionOrder(t *testing.T) {
	m, database, editor, _ := round290Module(t)
	editor.Viewer.Caps[CapArticlesEditAny] = struct{}{}
	editor.Viewer.Caps[CapArticlesEditAuthor] = struct{}{}
	now := time.Date(2026, 10, 14, 0, 0, 0, 0, time.UTC)
	editor.Clock = clock.Fixed(now)
	draft := round290Create(t, m, editor, "Unapproved time", "Body")
	scheduled := round290Create(t, m, editor, "Approved time", "Body")
	expired := round290Create(t, m, editor, "Expired", "Body")
	live := round290Create(t, m, editor, "Live", "Body")
	future := db.FormatUTC(now.Add(time.Hour))
	err := database.WriteTx(editor.Context, func(c context.Context, tx *db.Tx) error {
		for _, id := range []int64{scheduled.ID, expired.ID} {
			if _, err := tx.ExecContext(c, "UPDATE page_revisions SET created_at=? WHERE page_id=?", db.FormatUTC(now), id); err != nil {
				return err
			}
		}
		for _, id := range []int64{draft.ID, scheduled.ID} {
			if _, err := tx.ExecContext(c, "UPDATE pages SET go_live_at=? WHERE id=?", future, id); err != nil {
				return err
			}
		}
		if _, err := tx.ExecContext(c, "UPDATE page_revisions SET approved_go_live_at=? WHERE page_id=?", future, scheduled.ID); err != nil {
			return err
		}
		if _, err := tx.ExecContext(c, "UPDATE pages SET expired=1 WHERE id=?", expired.ID); err != nil {
			return err
		}
		if _, err := tx.ExecContext(c, "UPDATE pages SET live=1,updated_at=? WHERE id=?", future, live.ID); err != nil {
			return err
		}
		if _, err := tx.ExecContext(c, "UPDATE page_revisions SET created_at=? WHERE page_id=?", db.FormatUTC(now.Add(-time.Hour)), live.ID); err != nil {
			return err
		}
		if _, err := tx.ExecContext(c, "UPDATE page_revisions SET created_at=? WHERE page_id=?", future, draft.ID); err != nil {
			return err
		}
		if _, err := tx.ExecContext(c, "INSERT INTO broadcasts(kind,object_id,audience,waits_for_publish,created_at) VALUES('article',?,'everyone',1,?)", scheduled.ID, db.FormatUTC(now)); err != nil {
			return err
		}
		for range 2 {
			if _, err := tx.ExecContext(c, "INSERT INTO broadcasts(kind,object_id,audience,created_at) VALUES('article',?,'everyone',?)", live.ID, db.FormatUTC(now)); err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	all, err := m.listEditableArticles(editor, AdminListArticlesIn{})
	if err != nil {
		t.Fatal(err)
	}
	if all.PageSize != 30 || len(all.Items) != 4 || all.Items[0].ID != draft.ID || all.Items[3].ID != live.ID {
		t.Fatalf("list must use latest revision time and legacy page size: %+v", all)
	}
	for _, article := range all.Items {
		switch article.ID {
		case draft.ID:
			if article.ApprovedSchedule || article.CanAnnounce {
				t.Fatalf("unapproved draft became scheduled: %+v", article)
			}
		case scheduled.ID:
			if !article.ApprovedSchedule || article.CanAnnounce {
				t.Fatalf("waiting notification must not be offered twice: %+v", article)
			}
		case expired.ID:
			if !article.Expired {
				t.Fatal("expired state missing")
			}
		case live.ID:
			if article.Announced != 2 || !article.CanAnnounce {
				t.Fatalf("live repeat announcement lost: %+v", article)
			}
		}
	}
	for state, want := range map[string]int64{"draft": draft.ID, "scheduled": scheduled.ID} {
		filtered, err := m.listEditableArticles(editor, AdminListArticlesIn{Status: state})
		if err != nil || len(filtered.Items) != 1 || filtered.Items[0].ID != want {
			t.Fatalf("%s filter: %+v %v", state, filtered, err)
		}
	}
	subject, err := m.svc.AnnounceKind().Load(editor.Context, database.ReadPool(), draft.ID)
	if err != nil || subject == nil || subject.GoLiveAt != nil {
		t.Fatalf("direct announcement exposed unapproved time: %+v %v", subject, err)
	}
}

func TestAdminArticleAuthorLabelsExposeEmailOnlyToSuperuser(t *testing.T) {
	m, _, editor, _ := round290Module(t)
	editor.Viewer.Caps[CapArticlesEditAny] = struct{}{}
	editor.Viewer.Caps[CapArticlesEditAuthor] = struct{}{}
	projection, err := m.newArticleEditor(editor, struct{}{})
	if err != nil || len(projection.Authors) != 2 {
		t.Fatalf("editor authors: %+v %v", projection.Authors, err)
	}
	for _, author := range projection.Authors {
		if strings.Contains(author.Label, "@") || !strings.Contains(author.Label, "（#") {
			t.Fatalf("ordinary editor author label leaks email: %+v", author)
		}
	}
	editor.Viewer.Superuser = true
	projection, err = m.newArticleEditor(editor, struct{}{})
	if err != nil {
		t.Fatal(err)
	}
	for _, author := range projection.Authors {
		if !strings.Contains(author.Label, "@") {
			t.Fatalf("superuser author label cannot distinguish users: %+v", author)
		}
	}
}
