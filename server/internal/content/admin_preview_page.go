package content

import (
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/comments"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/markdown"
)

// articlePreviewPage exposes only a draft the actor can edit. It does not
// publish, modify the live row, or weaken the public article endpoint's gate.
type ArticlePreviewPageIn struct {
	ID       api.ID `path:"id"`
	Sort     string `query:"sort"`
	Comments int    `query:"comments"`
}

func (m *Module) articlePreviewPage(ctx *app.Ctx, in ArticlePreviewPageIn) (NewsDetailOut, error) {
	article, err := m.authorizedArticle(ctx, int64(in.ID))
	if err != nil {
		return NewsDetailOut{}, err
	}
	draft := articleDraft(article)
	latest, err := m.svc.store.GetLatestRevision(ctx.Context, article.ID)
	if err != nil {
		return NewsDetailOut{}, err
	}
	if latest != nil {
		draft, err = readArticleRevisionContent(latest.Content, draft)
		if err != nil {
			return NewsDetailOut{}, err
		}
	}
	preview := *article
	preview.Title, preview.Slug = draft.Title, draft.Slug
	preview.Summary, preview.BodyMD = draft.Summary, draft.BodyMD
	preview.CategoryID, preview.CoverImageID = draft.CategoryID, draft.CoverImageID
	preview.AuthorID, preview.RelatedTournamentID = draft.AuthorID, draft.RelatedTournamentID
	preview.CommentsEnabled = draft.CommentsEnabled
	preview.SeoTitle, preview.SearchDescription = draft.SeoTitle, draft.SearchDescription
	rendered, stats, err := markdown.Render(draft.BodyMD, m.svc.siteURL, nil)
	if err != nil {
		return NewsDetailOut{}, err
	}
	preview.BodyHTML, _ = markdown.AnchorHeadings(rendered)
	preview.BodyPlain = markdown.PlainHTML(rendered)
	preview.CharCount = markdown.WordCount(preview.BodyPlain)
	preview.ReadingTime = markdown.ReadingMinutes(preview.CharCount, stats.Images, stats.Videos)
	preview.CategoryName = ""
	if draft.CategoryID != nil {
		category, err := m.svc.store.GetCategoryByID(ctx.Context, *draft.CategoryID)
		if err != nil {
			return NewsDetailOut{}, err
		}
		if category != nil {
			preview.CategoryName = category.Name
		}
	}
	out, err := m.svc.articleProjection(ctx, &preview)
	if err != nil {
		return out, err
	}
	out.Thread = &comments.ListCommentsResult{Page: 1, PageSize: 20, Comments: []*comments.Comment{}}
	if article.Live && article.Public && m.comments != nil {
		out.Thread, err = m.comments.ListComments(ctx, article.ID, comments.ListCommentsInput{SortBy: in.Sort, Page: in.Comments, PageSize: 20})
	}
	return out, err
}
