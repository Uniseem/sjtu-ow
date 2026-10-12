package content

import (
	"net/http"
	"strings"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

func TestArticlePreviewPageUsesLatestDraftWithoutPublishingOrLeaking(t *testing.T) {
	m, database, owner, other := round290Module(t)
	draft := round290Create(t, m, owner, "private draft title", "## Private draft\n\nUnpublished secret.")
	stored, err := m.svc.store.GetArticleByID(owner.Context, draft.ID)
	if err != nil {
		t.Fatal(err)
	}
	_, err = m.svc.ArticlePage(owner, stored.Slug)
	round290ErrorStatus(t, err, http.StatusNotFound)

	preview, err := m.articlePreviewPage(owner, ArticlePreviewPageIn{ID: api.ID(draft.ID)})
	if err != nil || preview.Title != "private draft title" || !strings.Contains(preview.BodyHTML, "Unpublished secret.") || preview.Thread == nil || len(preview.Thread.Comments) != 0 {
		t.Fatalf("draft projection lost actual content: %+v %v", preview, err)
	}
	denied, err := m.articlePreviewPage(other, ArticlePreviewPageIn{ID: api.ID(draft.ID)})
	round290ErrorStatus(t, err, http.StatusNotFound)
	if denied.Title != "" || denied.BodyHTML != "" {
		t.Fatal("private draft escaped through denied projection")
	}
	// The live row deliberately differs from the latest draft. Preview must not
	// substitute that live content or update it while composing the response.
	if _, err := database.WritePool().Exec(`UPDATE pages SET live=1,title='Live title' WHERE id=?`, draft.ID); err != nil {
		t.Fatal(err)
	}
	preview, err = m.articlePreviewPage(owner, ArticlePreviewPageIn{ID: api.ID(draft.ID)})
	if err != nil || preview.Title != "private draft title" {
		t.Fatalf("preview used live title: %q %v", preview.Title, err)
	}
	stored, err = m.svc.store.GetArticleByID(owner.Context, draft.ID)
	if err != nil || stored.Title != "Live title" || !stored.Live {
		t.Fatal("preview changed the live article")
	}
}
