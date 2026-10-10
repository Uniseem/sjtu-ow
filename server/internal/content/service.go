package content

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/notify"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/markdown"
)

// ContentCaps 定义内容域用到的能力常量。
const (
	CapArticlesEditAny    app.Cap = "articles.edit_any"
	CapArticlesEditAuthor app.Cap = "articles.edit_author"
	CapArticlesPublishOwn app.Cap = "articles.publish_own"
	CapCategoriesManage   app.Cap = "article_categories.manage"
	CapSitePagesManage    app.Cap = "site_pages.manage"
)

// Service 协调内容域业务逻辑。
type Service struct {
	store   *Store
	siteURL string
	mod     app.ModerationSink
	// testEnvironment 为真时 robots.txt 整站不让抓（设计 16.10）。
	testEnvironment bool
}

// SetModeration 接上内容审核的送审入口：文章发布时把标题、摘要、正文（Markdown 原文）送审（规则 186）。
func (s *Service) SetModeration(m app.ModerationSink) { s.mod = m }

// NewService 创建内容域服务。
func NewService(store *Store, siteURL string) *Service {
	return &Service{
		store:   store,
		siteURL: strings.TrimRight(siteURL, "/"),
	}
}

// Store 返回底层的 Store。
func (s *Service) Store() *Store {
	return s.store
}

// canEditArticle 校验是否具备编辑/管理该文章的权限（规则 49）。
func (s *Service) canEditArticle(v *app.Viewer, p *Page) bool {
	if v == nil || v.Disabled || v.ID <= 0 {
		return false
	}
	if v.Superuser || v.HasCap(CapArticlesEditAny) {
		return true
	}
	return p.OwnerID != nil && *p.OwnerID == v.ID
}

// canEditAuthor 校验是否可以修改作者（规则 52）。
func (s *Service) canEditAuthor(v *app.Viewer) bool {
	if v == nil || v.Disabled || v.ID <= 0 {
		return false
	}
	return v.Superuser || v.HasCap(CapArticlesEditAuthor)
}

// canEditScheduleAndSlug 校验是否可以修改 slug、SEO 与定时字段（规则 51）。
func (s *Service) canEditScheduleAndSlug(v *app.Viewer) bool {
	if v == nil || v.Disabled || v.ID <= 0 {
		return false
	}
	return v.Superuser || v.HasCap(CapArticlesEditAny)
}

// isPureSubmitter 校验是否为纯投稿者（规则 53）。
func (s *Service) isPureSubmitter(v *app.Viewer) bool {
	if v == nil || v.Superuser {
		return false
	}
	return !v.HasCap(CapArticlesEditAny) && !v.HasCap(CapArticlesPublishOwn)
}

// CreateDraftInput 创建草稿入参。
type CreateDraftInput struct {
	Title      string `json:"title"`
	CategoryID *int64 `json:"category_id"`
	Summary    string `json:"summary"`
	BodyMD     string `json:"body_md"`
}

// CreateDraftResult 创建草稿回执。
type CreateDraftResult struct {
	ID       int64  `json:"id"`
	Location string `json:"location"`
	Version  int64  `json:"version"`
}

// CreateDraft 创建初始草稿（规则 46，12 号文档 5.5）。
func (s *Service) CreateDraft(ctx *app.Ctx, in CreateDraftInput) (*CreateDraftResult, error) {
	if ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	if !ctx.Viewer.CanUse("article_submit") {
		return nil, api.Forbidden()
	}

	title := strings.TrimSpace(in.Title)
	if title == "" {
		title = "(无标题)"
	}

	baseSlug := Slugify(title)
	uniqueSlug, err := s.store.ResolveUniqueSlug(ctx.Context, KindArticle, baseSlug, 0)
	if err != nil {
		return nil, err
	}

	ownerID := ctx.Viewer.ID
	p := &Page{
		Kind:    KindArticle,
		Slug:    uniqueSlug,
		Title:   title,
		OwnerID: &ownerID,
		Live:    false,
		Version: 1,
	}

	a := &Article{
		CategoryID:      in.CategoryID,
		Summary:         in.Summary,
		BodyMD:          in.BodyMD,
		AuthorID:        &ownerID,
		CommentsEnabled: true,
	}

	revContent := ArticleRevisionContent{
		Title:           title,
		Slug:            uniqueSlug,
		CategoryID:      in.CategoryID,
		Summary:         in.Summary,
		BodyMD:          in.BodyMD,
		AuthorID:        &ownerID,
		CommentsEnabled: true,
	}
	revBytes, _ := json.Marshal(revContent)

	created, _, err := s.store.CreateArticleDraft(ctx.Context, p, a, string(revBytes), ownerID)
	if err != nil {
		return nil, err
	}

	return &CreateDraftResult{
		ID:       created.ID,
		Location: fmt.Sprintf("/admin/articles/%d", created.ID),
		Version:  created.Version,
	}, nil
}

// SaveDraftInput 自动保存入参（12 号文档 5.5）。
type SaveDraftInput struct {
	BaseVersion int64                  `json:"base_version"`
	Changes     map[string]interface{} `json:"changes"`
}

// SaveDraftResult 自动保存回执。
type SaveDraftResult struct {
	Version int64               `json:"version"`
	Saved   []string            `json:"saved"`
	Fields  map[string][]string `json:"fields,omitempty"`
	Values  map[string]any      `json:"values,omitempty"`
	SavedAt time.Time           `json:"saved_at"`
}

// SaveDraft 执行自动保存协议 v2（规则 43–47，12 号文档 5.5）。
func (s *Service) SaveDraft(ctx *app.Ctx, pageID int64, in SaveDraftInput) (*SaveDraftResult, error) {
	if ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}

	curArticle, err := s.store.GetArticleByID(ctx.Context, pageID)
	if err != nil {
		return nil, err
	}
	if curArticle == nil {
		return nil, api.NotFound("文章不存在")
	}
	if !s.canEditArticle(ctx.Viewer, &curArticle.Page) {
		return nil, api.Forbidden()
	}

	// 读当前最新修订
	latestRev, err := s.store.GetLatestRevision(ctx.Context, pageID)
	if err != nil {
		return nil, err
	}

	var revContent ArticleRevisionContent
	if latestRev != nil && latestRev.Content != "" {
		_ = json.Unmarshal([]byte(latestRev.Content), &revContent)
	} else {
		// 回落到当前行数据
		revContent = ArticleRevisionContent{
			Title:               curArticle.Title,
			Slug:                curArticle.Slug,
			CategoryID:          curArticle.CategoryID,
			CoverImageID:        curArticle.CoverImageID,
			Summary:             curArticle.Summary,
			BodyMD:              curArticle.BodyMD,
			AuthorID:            curArticle.AuthorID,
			CommentsEnabled:     curArticle.CommentsEnabled,
			RelatedTournamentID: curArticle.RelatedTournamentID,
			SeoTitle:            curArticle.SeoTitle,
			SearchDescription:   curArticle.SearchDescription,
			GoLiveAt:            curArticle.GoLiveAt,
			ExpireAt:            curArticle.ExpireAt,
		}
	}

	savedFields := make([]string, 0)
	fieldErrors := make(map[string][]string)
	retValues := make(map[string]any)

	// 部分保存与按字段校验（规则 47）
	for k, v := range in.Changes {
		switch k {
		case "title":
			if str, ok := v.(string); ok {
				revContent.Title = str
				savedFields = append(savedFields, "title")
			} else {
				fieldErrors["title"] = []string{"标题格式无效"}
			}
		case "summary":
			if str, ok := v.(string); ok {
				revContent.Summary = str
				savedFields = append(savedFields, "summary")
			} else {
				fieldErrors["summary"] = []string{"摘要格式无效"}
			}
		case "body_md":
			if str, ok := v.(string); ok {
				revContent.BodyMD = str
				savedFields = append(savedFields, "body_md")
			} else {
				fieldErrors["body_md"] = []string{"正文格式无效"}
			}
		case "category_id":
			if v == nil {
				revContent.CategoryID = nil
				savedFields = append(savedFields, "category_id")
			} else if num, ok := toInt64(v); ok {
				cat, err := s.store.GetCategoryByID(ctx.Context, num)
				if err != nil || cat == nil {
					fieldErrors["category_id"] = []string{"分类不存在"}
				} else if s.isPureSubmitter(ctx.Viewer) && !cat.AllowSubmission {
					fieldErrors["category_id"] = []string{"普通投稿者不可选该分类"}
				} else {
					revContent.CategoryID = &num
					savedFields = append(savedFields, "category_id")
				}
			} else {
				fieldErrors["category_id"] = []string{"分类 ID 无效"}
			}
		case "cover_image_id":
			if v == nil {
				revContent.CoverImageID = nil
				savedFields = append(savedFields, "cover_image_id")
			} else if num, ok := toInt64(v); ok {
				revContent.CoverImageID = &num
				savedFields = append(savedFields, "cover_image_id")
			} else {
				fieldErrors["cover_image_id"] = []string{"封面图 ID 无效"}
			}
		case "comments_enabled":
			if s.isPureSubmitter(ctx.Viewer) {
				fieldErrors["comments_enabled"] = []string{"普通投稿者不可更改评论设置"}
			} else if b, ok := v.(bool); ok {
				revContent.CommentsEnabled = b
				savedFields = append(savedFields, "comments_enabled")
			} else {
				fieldErrors["comments_enabled"] = []string{"评论开关格式无效"}
			}
		case "author_id":
			if !s.canEditAuthor(ctx.Viewer) {
				fieldErrors["author_id"] = []string{"仅内容编辑或超管可修改作者"}
			} else if v == nil {
				revContent.AuthorID = nil
				savedFields = append(savedFields, "author_id")
			} else if num, ok := toInt64(v); ok {
				revContent.AuthorID = &num
				savedFields = append(savedFields, "author_id")
			} else {
				fieldErrors["author_id"] = []string{"作者 ID 无效"}
			}
		case "slug":
			if !s.canEditScheduleAndSlug(ctx.Viewer) {
				fieldErrors["slug"] = []string{"普通成员不可修改网址片段"}
			} else if str, ok := v.(string); ok {
				str = strings.TrimSpace(str)
				if str != "" {
					avail, err := s.store.CheckSlugAvailable(ctx.Context, KindArticle, str, pageID)
					if err != nil || !avail {
						fieldErrors["slug"] = []string{"该网址片段已被使用"}
					} else {
						revContent.Slug = str
						savedFields = append(savedFields, "slug")
					}
				}
			}
		case "seo_title":
			if s.canEditScheduleAndSlug(ctx.Viewer) {
				if str, ok := v.(string); ok {
					revContent.SeoTitle = str
					savedFields = append(savedFields, "seo_title")
				}
			}
		case "search_description":
			if s.canEditScheduleAndSlug(ctx.Viewer) {
				if str, ok := v.(string); ok {
					revContent.SearchDescription = str
					savedFields = append(savedFields, "search_description")
				}
			}
		case "go_live_at":
			if !s.canEditScheduleAndSlug(ctx.Viewer) {
				fieldErrors["go_live_at"] = []string{"普通成员不可设置定时上线"}
			} else if v == nil {
				revContent.GoLiveAt = nil
				savedFields = append(savedFields, "go_live_at")
			} else if str, ok := v.(string); ok {
				t, err := time.Parse(time.RFC3339, str)
				if err != nil {
					fieldErrors["go_live_at"] = []string{"时间格式无效"}
				} else {
					revContent.GoLiveAt = &t
					savedFields = append(savedFields, "go_live_at")
				}
			}
		case "expire_at":
			if !s.canEditScheduleAndSlug(ctx.Viewer) {
				fieldErrors["expire_at"] = []string{"普通成员不可设置到期撤下"}
			} else if v == nil {
				revContent.ExpireAt = nil
				savedFields = append(savedFields, "expire_at")
			} else if str, ok := v.(string); ok {
				t, err := time.Parse(time.RFC3339, str)
				if err != nil {
					fieldErrors["expire_at"] = []string{"时间格式无效"}
				} else {
					revContent.ExpireAt = &t
					savedFields = append(savedFields, "expire_at")
				}
			}
		}
	}

	// 规则 57：expire_at 必须晚于 go_live_at 且在将来
	if revContent.ExpireAt != nil {
		if revContent.ExpireAt.Before(ctx.Now()) {
			fieldErrors["expire_at"] = []string{"到期时间必须在未来"}
		}
		if revContent.GoLiveAt != nil && revContent.ExpireAt.Before(*revContent.GoLiveAt) {
			fieldErrors["expire_at"] = []string{"到期时间必须晚于上线时间"}
		}
	}

	// 复用修订判定（规则 43–44）：
	// 仅当最新修订是本人的草稿、非 live、未定时、且 30 分钟内创建时 overwrite
	var overwriteRevID int64
	if latestRev != nil && !curArticle.Live {
		isSameAuthor := latestRev.AuthorID != nil && *latestRev.AuthorID == ctx.Viewer.ID
		isRecent := ctx.Now().Sub(latestRev.CreatedAt) < 30*time.Minute
		isNotScheduled := latestRev.ApprovedGoLiveAt == nil
		if isSameAuthor && isRecent && isNotScheduled {
			overwriteRevID = latestRev.ID
		}
	}

	newBytes, _ := json.Marshal(revContent)
	newVer, _, err := s.store.SaveArticleDraft(ctx.Context, pageID, in.BaseVersion, string(newBytes), ctx.Viewer.ID, overwriteRevID)
	if err != nil {
		return nil, err
	}

	return &SaveDraftResult{
		Version: newVer,
		Saved:   savedFields,
		Fields:  fieldErrors,
		Values:  retValues,
		SavedAt: ctx.Now(),
	}, nil
}

// PublishInput 发布文章入参。
type PublishInput struct {
	BaseVersion int64 `json:"base_version"`
}

// Publish 发布文章（规则 46, 58–72）。
func (s *Service) Publish(ctx *app.Ctx, pageID int64, in PublishInput) (*Article, error) {
	if ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}

	curArticle, err := s.store.GetArticleByID(ctx.Context, pageID)
	if err != nil {
		return nil, err
	}
	if curArticle == nil {
		return nil, api.NotFound("文章不存在")
	}
	if !s.canEditArticle(ctx.Viewer, &curArticle.Page) {
		return nil, api.Forbidden()
	}

	latestRev, err := s.store.GetLatestRevision(ctx.Context, pageID)
	if err != nil {
		return nil, err
	}
	if latestRev == nil {
		return nil, api.Invalid("没有可发布的修订版本")
	}

	var revContent ArticleRevisionContent
	if err := json.Unmarshal([]byte(latestRev.Content), &revContent); err != nil {
		return nil, api.Invalid("修订内容损坏")
	}

	// 整表单校验（规则 46）
	title := strings.TrimSpace(revContent.Title)
	if title == "" || title == "(无标题)" {
		return nil, api.Invalid("文章标题不能为空")
	}
	if revContent.CategoryID == nil {
		return nil, api.Invalid("必须选择文章分类")
	}
	if strings.TrimSpace(revContent.BodyMD) == "" {
		return nil, api.Invalid("文章正文不能为空")
	}

	// 规则 58–59：若 slug 为空则自动生成
	slug := strings.TrimSpace(revContent.Slug)
	if slug == "" {
		slug = Slugify(title)
	}
	uniqueSlug, err := s.store.ResolveUniqueSlug(ctx.Context, KindArticle, slug, pageID)
	if err != nil {
		return nil, err
	}

	// 规则 61–72：Markdown 渲染与元数据提取
	rawHTML, stats, err := markdown.Render(revContent.BodyMD, s.siteURL, nil)
	if err != nil {
		return nil, api.Invalid("Markdown 渲染失败")
	}
	anchoredHTML, headings := markdown.AnchorHeadings(rawHTML)
	var html string
	if len(headings) >= 3 {
		html = anchoredHTML
	} else {
		html = rawHTML
	}

	bodyPlain := markdown.PlainHTML(html)
	wordCount := markdown.WordCount(bodyPlain)
	readingTime := markdown.ReadingMinutes(wordCount, stats.Images, stats.Videos)
	searchText := strings.ToLower(fmt.Sprintf("%s\n%s\n%s", title, revContent.Summary, bodyPlain))

	p := curArticle.Page
	p.Title = title
	p.Slug = uniqueSlug
	p.SeoTitle = revContent.SeoTitle
	p.SearchDescription = revContent.SearchDescription
	p.GoLiveAt = revContent.GoLiveAt
	p.ExpireAt = revContent.ExpireAt

	// 规则 54：若 go_live_at 在未来，不直接 live，待定时任务上线
	if p.GoLiveAt != nil && p.GoLiveAt.After(ctx.Now()) {
		p.Live = false
	} else {
		p.Live = true
	}

	a := *curArticle
	a.CategoryID = revContent.CategoryID
	a.CoverImageID = revContent.CoverImageID
	a.Summary = revContent.Summary
	a.BodyMD = revContent.BodyMD
	a.BodyHTML = html
	a.BodyPlain = bodyPlain
	a.CharCount = wordCount
	a.ReadingTime = readingTime
	a.AuthorID = revContent.AuthorID
	a.CommentsEnabled = revContent.CommentsEnabled
	a.RelatedTournamentID = revContent.RelatedTournamentID
	a.SearchText = searchText

	if err := s.store.PublishArticle(ctx.Context, pageID, &p, &a, latestRev.ID); err != nil {
		return nil, err
	}

	if s.mod != nil {
		text := strings.TrimSpace(strings.Join([]string{title, revContent.Summary, revContent.BodyMD}, "\n\n"))
		var author int64
		if a.AuthorID != nil {
			author = *a.AuthorID
		}
		if err := s.mod.Submit(ctx.Context, "article", pageID, "content", text, "/news/"+uniqueSlug+"/", author); err != nil {
			slog.Warn("文章送审失败", "id", pageID, "err", err.Error())
		}
	}

	return s.store.GetArticleByID(ctx.Context, pageID)
}

// Unpublish 撤下文章（规则 49, 56）。
func (s *Service) Unpublish(ctx *app.Ctx, pageID int64) error {
	if ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return api.Unauthorized("要先登录")
	}

	curArticle, err := s.store.GetArticleByID(ctx.Context, pageID)
	if err != nil {
		return err
	}
	if curArticle == nil {
		return api.NotFound("文章不存在")
	}
	if !s.canEditArticle(ctx.Viewer, &curArticle.Page) {
		return api.Forbidden()
	}

	return s.store.UnpublishArticle(ctx.Context, pageID)
}

// Delete 删除文章。
func (s *Service) Delete(ctx *app.Ctx, pageID int64) error {
	if ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return api.Unauthorized("要先登录")
	}

	curArticle, err := s.store.GetArticleByID(ctx.Context, pageID)
	if err != nil {
		return err
	}
	if curArticle == nil {
		return api.NotFound("文章不存在")
	}
	if !s.canEditArticle(ctx.Viewer, &curArticle.Page) {
		return api.Forbidden()
	}

	return s.store.DeleteArticle(ctx.Context, pageID)
}

// CheckScheduledWorker 由后台 worker 每 30 秒执行一次定时发布与到期撤下（规则 54–57）。
func (s *Service) CheckScheduledWorker(ctx context.Context, now time.Time) error {
	nowStr := now.UTC().Format(time.RFC3339Nano)

	// 1. 到期上线：live=0 且 go_live_at <= now 且 (expire_at IS NULL OR expire_at > now)
	rows, err := s.store.d.ReadPool().QueryContext(ctx, `
		SELECT id FROM pages
		WHERE kind = 'article' AND live = 0 AND go_live_at IS NOT NULL AND go_live_at <= ?
		  AND (expire_at IS NULL OR expire_at > ?)
	`, nowStr, nowStr)
	if err == nil {
		defer rows.Close()
		var ids []int64
		for rows.Next() {
			var id int64
			if err := rows.Scan(&id); err == nil {
				ids = append(ids, id)
			}
		}
		for _, id := range ids {
			_ = s.store.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
				if _, err := tx.ExecContext(txCtx, `
					UPDATE pages SET live = 1, last_published_at = ?, version = version + 1
					WHERE id = ?
				`, nowStr, id); err != nil {
					return err
				}
				// 上线那一刻放出「上线时通知全体成员」（规则 55）
				_, err := notify.SendWaiting(txCtx, tx, notify.KindArticle, id, now)
				return err
			})
		}
	}

	// 2. 到期撤下：live=1 且 expire_at IS NOT NULL 且 expire_at <= now
	expRows, err := s.store.d.ReadPool().QueryContext(ctx, `
		SELECT id FROM pages
		WHERE kind = 'article' AND live = 1 AND expire_at IS NOT NULL AND expire_at <= ?
	`, nowStr)
	if err == nil {
		defer expRows.Close()
		var ids []int64
		for expRows.Next() {
			var id int64
			if err := expRows.Scan(&id); err == nil {
				ids = append(ids, id)
			}
		}
		for _, id := range ids {
			_ = s.store.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
				_, err := tx.ExecContext(txCtx, `
					UPDATE pages SET live = 0, version = version + 1
					WHERE id = ?
				`, id)
				return err
			})
		}
	}

	return nil
}

func toInt64(v any) (int64, bool) {
	switch val := v.(type) {
	case int:
		return int64(val), true
	case int64:
		return val, true
	case float64:
		return int64(val), true
	case json.Number:
		n, err := val.Int64()
		return n, err == nil
	default:
		return 0, false
	}
}
