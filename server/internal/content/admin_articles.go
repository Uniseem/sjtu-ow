package content

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type ArticleCapabilities struct {
	Edit         bool `json:"edit"`
	Publish      bool `json:"publish"`
	Unpublish    bool `json:"unpublish"`
	Delete       bool `json:"delete"`
	Announce     bool `json:"announce"`
	EditAuthor   bool `json:"edit_author"`
	EditComments bool `json:"edit_comments"`
	EditSchedule bool `json:"edit_schedule"`
}

type ArticleCategoryChoice struct {
	ID              int64  `json:"id"`
	Name            string `json:"name"`
	AllowSubmission bool   `json:"allow_submission"`
}

type ArticleAuthorChoice struct {
	ID       int64  `json:"id"`
	Nickname string `json:"nickname"`
	Label    string `json:"label"`
}
type ArticleTournamentChoice struct {
	ID    int64  `json:"id"`
	Title string `json:"title"`
}
type ArticleVerdict struct {
	ID        int64   `json:"id"`
	Risk      string  `json:"risk"`
	Reason    string  `json:"reason"`
	Quote     string  `json:"quote"`
	CheckedAt *string `json:"checked_at"`
}

func articleDraft(article *Article) ArticleRevisionContent {
	return ArticleRevisionContent{
		Title: article.Title, Slug: article.Slug, CategoryID: article.CategoryID,
		CoverImageID: article.CoverImageID, Summary: article.Summary, BodyMD: article.BodyMD,
		AuthorID: article.AuthorID, CommentsEnabled: article.CommentsEnabled,
		RelatedTournamentID: article.RelatedTournamentID, SeoTitle: article.SeoTitle,
		SearchDescription: article.SearchDescription, GoLiveAt: article.GoLiveAt, ExpireAt: article.ExpireAt,
	}
}

func (m *Module) editorProjection(ctx *app.Ctx, article *Article) (AdminArticleDetailOut, error) {
	out := AdminArticleDetailOut{
		Article: article, Categories: []ArticleCategoryChoice{}, Authors: []ArticleAuthorChoice{},
		Tournaments: []ArticleTournamentChoice{}, Guide: m.svc.isPlainWriter(ctx.Viewer),
	}
	if ctx.Viewer == nil || ctx.Viewer.Disabled {
		return out, api.Unauthorized("要先登录")
	}
	if article != nil && !m.svc.canEditArticle(ctx.Viewer, &article.Page) {
		return out, api.NotFound("文章不存在")
	}
	edit := article != nil || ctx.Viewer.CanUse("article_submit")
	out.Capabilities = ArticleCapabilities{
		Edit: edit, Publish: edit, Delete: article != nil && edit,
		Unpublish:  article != nil && article.Live && edit,
		Announce:   ctx.Viewer.HasCap(CapArticlesEditAny),
		EditAuthor: m.svc.canEditAuthor(ctx.Viewer), EditSchedule: m.svc.canEditScheduleAndSlug(ctx.Viewer),
		EditComments: !m.svc.isPureSubmitter(ctx.Viewer),
	}
	if article != nil {
		if err := m.readArticleAdminStates(ctx, []*Article{article}); err != nil {
			return out, err
		}
		out.Version = article.Version
		draft := articleDraft(article)
		latest, err := m.svc.store.GetLatestRevision(ctx.Context, article.ID)
		if err != nil {
			return out, err
		}
		if latest != nil {
			draft, err = readArticleRevisionContent(latest.Content, draft)
			if err != nil {
				return out, fmt.Errorf("读取文章草稿: %w", err)
			}
		}
		out.Revision = &draft
		preview := fmt.Sprintf("/api/admin/articles/%d/preview", article.ID)
		out.PreviewURL = &preview
		out.Announced = article.Announced
		out.Capabilities.Announce = article.CanAnnounce
		if ctx.Viewer.HasCap("moderation.review") {
			// The moderation record is read-only: displaying it never schedules AI work.
			verdict, err := m.articleVerdict(ctx.Context, article.ID)
			if err != nil {
				return out, err
			}
			out.Verdict = verdict
		}
	} else {
		author := ctx.Viewer.ID
		out.Revision = &ArticleRevisionContent{AuthorID: &author, CommentsEnabled: true}
	}
	categories, err := m.svc.store.ListCategories(ctx.Context)
	if err != nil {
		return out, err
	}
	for _, category := range categories {
		if strings.TrimSpace(category.Name) != "" && (!m.svc.isPureSubmitter(ctx.Viewer) || category.AllowSubmission) {
			out.Categories = append(out.Categories, ArticleCategoryChoice{ID: category.ID, Name: category.Name, AllowSubmission: category.AllowSubmission})
		}
	}
	if out.Capabilities.EditAuthor {
		rows, err := m.svc.store.d.ReadPool().QueryContext(ctx.Context, "SELECT id,nickname,email FROM users WHERE is_active=1 ORDER BY nickname,id")
		if err != nil {
			return out, err
		}
		for rows.Next() {
			var choice ArticleAuthorChoice
			var email string
			if err := rows.Scan(&choice.ID, &choice.Nickname, &email); err != nil {
				rows.Close()
				return out, err
			}
			choice.Label = fmt.Sprintf("%s（#%d）", choice.Nickname, choice.ID)
			if ctx.Viewer.Superuser {
				choice.Label = fmt.Sprintf("%s（%s）", choice.Nickname, email)
			}
			out.Authors = append(out.Authors, choice)
		}
		err = rows.Err()
		rows.Close()
		if err != nil {
			return out, err
		}
	}
	rows, err := m.svc.store.d.ReadPool().QueryContext(ctx.Context, "SELECT id,title FROM tournaments ORDER BY id DESC")
	if err != nil {
		return out, err
	}
	for rows.Next() {
		var choice ArticleTournamentChoice
		if err := rows.Scan(&choice.ID, &choice.Title); err != nil {
			rows.Close()
			return out, err
		}
		out.Tournaments = append(out.Tournaments, choice)
	}
	err = rows.Err()
	rows.Close()
	return out, err
}

func (m *Module) articleVerdict(ctx context.Context, id int64) (*ArticleVerdict, error) {
	var verdict ArticleVerdict
	var checked sql.NullString
	err := m.svc.store.d.ReadPool().QueryRowContext(ctx, `SELECT id,risk,reason,quote,checked_at FROM moderation_items
        WHERE target_type='article' AND target_id=? ORDER BY id DESC LIMIT 1`, id).Scan(
		&verdict.ID, &verdict.Risk, &verdict.Reason, &verdict.Quote, &checked,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if checked.Valid {
		verdict.CheckedAt = &checked.String
	}
	return &verdict, nil
}

func (m *Module) newArticleEditor(ctx *app.Ctx, _ struct{}) (AdminArticleDetailOut, error) {
	if !ctx.Viewer.CanUse("article_submit") {
		return AdminArticleDetailOut{}, api.Forbidden()
	}
	return m.editorProjection(ctx, nil)
}

func (m *Module) listEditableArticles(ctx *app.Ctx, in AdminListArticlesIn) (AdminListArticlesOut, error) {
	out := AdminListArticlesOut{Items: []*Article{}}
	if ctx.Viewer == nil {
		return out, api.Unauthorized("要先登录")
	}
	where := "p.kind='article'"
	args := []any{}
	if !ctx.Viewer.HasCap(CapArticlesEditAny) || in.Mine {
		where += " AND p.owner_id=?"
		args = append(args, ctx.Viewer.ID)
	}
	if in.Category != "" {
		if id, err := strconv.ParseInt(in.Category, 10, 64); err == nil && id > 0 {
			where += " AND a.category_id=?"
			args = append(args, id)
		} else {
			where += " AND c.slug=?"
			args = append(args, in.Category)
		}
	}
	switch in.Status {
	case "draft":
		where += " AND p.live=0 AND p.expired=0 AND NOT EXISTS(SELECT 1 FROM page_revisions schedule WHERE schedule.page_id=p.id AND schedule.approved_go_live_at IS NOT NULL)"
	case "live":
		where += " AND p.live=1"
	case "changed":
		where += " AND p.live=1 AND p.has_unpublished_changes=1"
	case "scheduled":
		where += " AND p.live=0 AND EXISTS(SELECT 1 FROM page_revisions schedule WHERE schedule.page_id=p.id AND schedule.approved_go_live_at IS NOT NULL)"
	case "":
	default:
		return out, api.InvalidFields(map[string][]string{"status": {"状态无效"}})
	}
	rows, err := m.svc.store.d.ReadPool().QueryContext(ctx.Context, `SELECT `+articleColumns+` FROM pages p JOIN articles a ON a.page_id=p.id
        LEFT JOIN article_categories c ON c.id=a.category_id LEFT JOIN users u ON u.id=a.author_id
        LEFT JOIN page_revisions latest ON latest.id=p.latest_revision_id WHERE `+where+` ORDER BY COALESCE(latest.created_at,p.updated_at) DESC,p.id DESC`, args...)
	if err != nil {
		return out, err
	}
	all := []*Article{}
	for rows.Next() {
		article, err := scanArticle(rows)
		if err != nil {
			rows.Close()
			return out, err
		}
		all = append(all, article)
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return out, err
	}
	if err := m.readArticleAdminStates(ctx, all); err != nil {
		return out, err
	}
	// Latest titles are read in one query instead of one query per table row.
	revisions, err := m.svc.store.d.ReadPool().QueryContext(ctx.Context, `SELECT p.id,r.content FROM pages p
        JOIN page_revisions r ON r.id=p.latest_revision_id WHERE p.kind='article'`)
	if err != nil {
		return out, err
	}
	titles := map[int64]string{}
	for revisions.Next() {
		var id int64
		var content string
		if err := revisions.Scan(&id, &content); err != nil {
			revisions.Close()
			return out, err
		}
		var draft ArticleRevisionContent
		if json.Unmarshal([]byte(content), &draft) == nil {
			titles[id] = draft.Title
		}
	}
	err = revisions.Err()
	revisions.Close()
	if err != nil {
		return out, err
	}
	query := strings.ToLower(strings.TrimSpace(in.Q))
	filtered := []*Article{}
	for _, article := range all {
		title, exists := titles[article.ID]
		if exists {
			article.DraftTitle = &title
		}
		if query != "" && !strings.Contains(strings.ToLower(title+" "+article.Title), query) {
			continue
		}
		filtered = append(filtered, article)
	}
	out.PageSize = in.PageSize
	if out.PageSize < 1 || out.PageSize > 100 {
		out.PageSize = 30
	}
	out.Total = len(filtered)
	last := max(1, (out.Total+out.PageSize-1)/out.PageSize)
	out.Page = in.Page
	if out.Page < 1 {
		out.Page = 1
	}
	if out.Page > last {
		out.Page = last
	}
	start := (out.Page - 1) * out.PageSize
	end := min(len(filtered), start+out.PageSize)
	if start < len(filtered) {
		out.Items = filtered[start:end]
	}
	return out, nil
}

type ArticleRevisionItem struct {
	ID        int64     `json:"id"`
	CreatedAt time.Time `json:"created_at"`
	UserID    *int64    `json:"user_id"`
	UserName  string    `json:"user_name"`
	Title     string    `json:"title"`
	Live      bool      `json:"live"`
	Latest    bool      `json:"latest"`
	Scheduled bool      `json:"scheduled"`
}

type ArticleRevisionListOut struct {
	Items                 []ArticleRevisionItem `json:"items"`
	CurrentVersion        int64                 `json:"current_version"`
	HasUnpublishedChanges bool                  `json:"has_unpublished_changes"`
}
type ArticleRevisionIn struct {
	ID       api.ID `path:"id"`
	Revision api.ID `path:"revision"`
}
type ArticleRevisionOut struct {
	Revision   ArticleRevisionItem    `json:"revision"`
	Draft      ArticleRevisionContent `json:"draft"`
	PreviewURL *string                `json:"preview_url"`
	CanRestore bool                   `json:"can_restore"`
	Version    int64                  `json:"version"`
}
type RestoreRevisionIn struct {
	ID          api.ID `path:"id"`
	Revision    api.ID `path:"revision"`
	BaseVersion int64  `json:"base_version"`
}
type RestoreRevisionOut struct {
	Version int64 `json:"version"`
}

func (m *Module) authorizedArticle(ctx *app.Ctx, id int64) (*Article, error) {
	article, err := m.svc.store.GetArticleByID(ctx.Context, id)
	if err != nil {
		return nil, err
	}
	if article == nil || !m.svc.canEditArticle(ctx.Viewer, &article.Page) {
		return nil, api.NotFound("文章不存在")
	}
	return article, nil
}

func revisionItem(article *Article, rev *PageRevision, name string, title string) ArticleRevisionItem {
	return ArticleRevisionItem{ID: rev.ID, CreatedAt: rev.CreatedAt, UserID: rev.AuthorID, UserName: name, Title: title,
		Live:      article.LiveRevisionID != nil && *article.LiveRevisionID == rev.ID,
		Latest:    article.LatestRevisionID != nil && *article.LatestRevisionID == rev.ID,
		Scheduled: rev.ApprovedGoLiveAt != nil,
	}
}

func (m *Module) articleRevisions(ctx *app.Ctx, in AdminArticleDetailIn) (ArticleRevisionListOut, error) {
	out := ArticleRevisionListOut{Items: []ArticleRevisionItem{}}
	article, err := m.authorizedArticle(ctx, int64(in.ID))
	if err != nil {
		return out, err
	}
	out.CurrentVersion = article.Version
	out.HasUnpublishedChanges = article.HasUnpublishedChanges
	rows, err := m.svc.store.d.ReadPool().QueryContext(ctx.Context, `SELECT r.id,r.author_id,r.content,r.created_at,r.approved_go_live_at,COALESCE(u.nickname,'')
        FROM page_revisions r LEFT JOIN users u ON u.id=r.author_id WHERE r.page_id=? ORDER BY r.id DESC`, article.ID)
	if err != nil {
		return out, err
	}
	defer rows.Close()
	for rows.Next() {
		rev := PageRevision{PageID: article.ID}
		var created, name string
		var approved sql.NullString
		if err := rows.Scan(&rev.ID, &rev.AuthorID, &rev.Content, &created, &approved, &name); err != nil {
			return out, err
		}
		rev.CreatedAt, _ = db.ParseUTC(created)
		if approved.Valid {
			at, err := db.ParseUTC(approved.String)
			if err == nil {
				rev.ApprovedGoLiveAt = &at
			}
		}
		var draft ArticleRevisionContent
		object, err := revisionObject(rev.Content)
		if err != nil {
			return out, fmt.Errorf("修订%d内容损坏: %w", rev.ID, err)
		}
		if err := revisionText(object, &draft.Title, "title"); err != nil {
			return out, err
		}
		out.Items = append(out.Items, revisionItem(article, &rev, name, draft.Title))
	}
	return out, rows.Err()
}

func (m *Module) articleRevision(ctx *app.Ctx, in ArticleRevisionIn) (ArticleRevisionOut, error) {
	out := ArticleRevisionOut{}
	article, err := m.authorizedArticle(ctx, int64(in.ID))
	if err != nil {
		return out, err
	}
	rev := PageRevision{PageID: article.ID}
	var created, name string
	var approved sql.NullString
	err = m.svc.store.d.ReadPool().QueryRowContext(ctx.Context, `SELECT r.id,r.author_id,r.content,r.created_at,r.approved_go_live_at,COALESCE(u.nickname,'')
        FROM page_revisions r LEFT JOIN users u ON u.id=r.author_id WHERE r.page_id=? AND r.id=?`, article.ID, int64(in.Revision)).Scan(
		&rev.ID, &rev.AuthorID, &rev.Content, &created, &approved, &name)
	if errors.Is(err, sql.ErrNoRows) {
		return out, api.NotFound("修订不存在")
	}
	if err != nil {
		return out, err
	}
	rev.CreatedAt, _ = db.ParseUTC(created)
	if approved.Valid {
		at, err := db.ParseUTC(approved.String)
		if err == nil {
			rev.ApprovedGoLiveAt = &at
		}
	}
	out.Draft, err = readArticleRevisionContent(rev.Content, articleDraft(article))
	if err != nil {
		return out, fmt.Errorf("修订内容损坏: %w", err)
	}
	out.Revision = revisionItem(article, &rev, name, out.Draft.Title)
	out.Version = article.Version
	out.CanRestore = true
	preview := fmt.Sprintf("/api/admin/articles/%d/preview?revision=%d", article.ID, rev.ID)
	out.PreviewURL = &preview
	return out, nil
}

func (m *Module) restoreRevision(ctx *app.Ctx, in RestoreRevisionIn) (RestoreRevisionOut, error) {
	detail, err := m.articleRevision(ctx, ArticleRevisionIn{ID: in.ID, Revision: in.Revision})
	if err != nil {
		return RestoreRevisionOut{}, err
	}
	// Restoring history is a write, so the current viewer's field permissions
	// still apply. Keep restricted fields from the current draft, not history.
	article, err := m.authorizedArticle(ctx, int64(in.ID))
	if err != nil {
		return RestoreRevisionOut{}, err
	}
	if article.Version != in.BaseVersion {
		return RestoreRevisionOut{}, articleStale(ctx.Context, m.svc.store.d.ReadPool(), article.ID)
	}
	current := articleDraft(article)
	latest, err := m.svc.store.GetLatestRevision(ctx.Context, article.ID)
	if err != nil {
		return RestoreRevisionOut{}, err
	}
	if latest != nil {
		current, err = readArticleRevisionContent(latest.Content, current)
		if err != nil {
			return RestoreRevisionOut{}, err
		}
	}
	if !m.svc.canEditAuthor(ctx.Viewer) {
		detail.Draft.AuthorID = current.AuthorID
	}
	if m.svc.isPureSubmitter(ctx.Viewer) {
		detail.Draft.CommentsEnabled = current.CommentsEnabled
	}
	if !m.svc.canEditScheduleAndSlug(ctx.Viewer) {
		detail.Draft.Slug = current.Slug
		detail.Draft.SeoTitle = current.SeoTitle
		detail.Draft.SearchDescription = current.SearchDescription
		detail.Draft.GoLiveAt = current.GoLiveAt
		detail.Draft.ExpireAt = current.ExpireAt
	}
	raw, err := json.Marshal(detail.Draft)
	if err != nil {
		return RestoreRevisionOut{}, err
	}
	var checks map[string]any
	if err := json.Unmarshal(raw, &checks); err != nil {
		return RestoreRevisionOut{}, err
	}
	// Unchanged protected fields are preserved, not submitted for editing.
	if !m.svc.canEditAuthor(ctx.Viewer) {
		delete(checks, "author_id")
	}
	if m.svc.isPureSubmitter(ctx.Viewer) {
		delete(checks, "comments_enabled")
	}
	if !m.svc.canEditScheduleAndSlug(ctx.Viewer) {
		for _, key := range []string{"slug", "seo_title", "search_description", "go_live_at", "expire_at"} {
			delete(checks, key)
		}
	}
	fields, err := m.svc.validateArticleChangesWithCover(ctx, checks, current.CoverImageID)
	if err != nil {
		return RestoreRevisionOut{}, err
	}
	if len(fields) > 0 {
		return RestoreRevisionOut{}, api.InvalidFields(fields)
	}
	version, _, err := m.svc.store.SaveArticleDraft(ctx.Context, int64(in.ID), in.BaseVersion, string(raw), ctx.Viewer.ID, 0, coverWriteCheck(ctx.Viewer, detail.Draft.CoverImageID, current.CoverImageID))
	return RestoreRevisionOut{Version: version}, err
}
