package content

import (
	"time"
)

// Kind 常量表示页面类型。
const (
	KindArticle   = "article"
	KindSitePage  = "site_page"
	KindNewsIndex = "news_index"
)

// Category 是文章分类。
type Category struct {
	ID              int64     `json:"id"`
	Name            string    `json:"name"`
	Slug            string    `json:"slug"`
	Description     string    `json:"description"`
	SortOrder       int       `json:"sort_order"`
	AllowSubmission bool      `json:"allow_submission"`
	Version         int64     `json:"version"`
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`
	ArticleCount    int       `json:"article_count,omitempty"`
}

// Page 是所有页面的公共基础数据。
type Page struct {
	ID                    int64      `json:"id"`
	Kind                  string     `json:"kind"`
	Slug                  string     `json:"slug"`
	Title                 string     `json:"title"`
	Live                  bool       `json:"live"`
	HasUnpublishedChanges bool       `json:"has_unpublished_changes"`
	GoLiveAt              *time.Time `json:"go_live_at,omitempty"`
	ExpireAt              *time.Time `json:"expire_at,omitempty"`
	FirstPublishedAt      *time.Time `json:"first_published_at,omitempty"`
	LastPublishedAt       *time.Time `json:"last_published_at,omitempty"`
	LiveRevisionID        *int64     `json:"live_revision_id,omitempty"`
	LatestRevisionID      *int64     `json:"latest_revision_id,omitempty"`
	OwnerID               *int64     `json:"owner_id,omitempty"`
	SeoTitle              string     `json:"seo_title"`
	SearchDescription     string     `json:"search_description"`
	Version               int64      `json:"version"`
	CreatedAt             time.Time  `json:"created_at"`
	UpdatedAt             time.Time  `json:"updated_at"`
}

// Article 表示资讯文章完整实体（含页面基础属性）。
type Article struct {
	Page
	CategoryID          *int64 `json:"category_id,omitempty"`
	CategoryName        string `json:"category_name,omitempty"`
	CoverImageID        *int64 `json:"cover_image_id,omitempty"`
	Summary             string `json:"summary"`
	BodyMD              string `json:"body_md"`
	BodyHTML            string `json:"body_html"`
	BodyPlain           string `json:"body_plain"`
	CharCount           int    `json:"char_count"`
	ReadingTime         int    `json:"reading_time"`
	AuthorID            *int64 `json:"author_id,omitempty"`
	AuthorName          string `json:"author_name,omitempty"`
	CommentsEnabled     bool   `json:"comments_enabled"`
	RelatedTournamentID *int64 `json:"related_tournament_id,omitempty"`
	SearchText          string `json:"search_text"`
	RendererVersion     int    `json:"renderer_version"`
}

// ArticleRevisionContent 是序列化存储在 page_revisions.content 中的文章草稿内容。
type ArticleRevisionContent struct {
	Title               string     `json:"title"`
	Slug                string     `json:"slug"`
	CategoryID          *int64     `json:"category_id"`
	CoverImageID        *int64     `json:"cover_image_id"`
	Summary             string     `json:"summary"`
	BodyMD              string     `json:"body_md"`
	AuthorID            *int64     `json:"author_id"`
	CommentsEnabled     bool       `json:"comments_enabled"`
	RelatedTournamentID *int64     `json:"related_tournament_id"`
	SeoTitle            string     `json:"seo_title"`
	SearchDescription   string     `json:"search_description"`
	GoLiveAt            *time.Time `json:"go_live_at"`
	ExpireAt            *time.Time `json:"expire_at"`
}

// PageRevision 表示页面历史修订。
type PageRevision struct {
	ID               int64      `json:"id"`
	PageID           int64      `json:"page_id"`
	AuthorID         *int64     `json:"author_id,omitempty"`
	Content          string     `json:"content"`
	CreatedAt        time.Time  `json:"created_at"`
	ApprovedGoLiveAt *time.Time `json:"approved_go_live_at,omitempty"`
}

// SitePage 表示关于、隐私、协议等单页。
type SitePage struct {
	Page
	BodyMD    string `json:"body_md"`
	BodyHTML  string `json:"body_html"`
	BodyPlain string `json:"body_plain"`
}

// HomePin 表示首页置顶。
type HomePin struct {
	ArticlePageID int64    `json:"article_page_id"`
	SortOrder     int      `json:"sort_order"`
	Article       *Article `json:"article,omitempty"`
}

// Broadcast 记录文章群发通知历史。
type Broadcast struct {
	ID             int64     `json:"id"`
	ArticleID      int64     `json:"article_id"`
	SenderID       *int64    `json:"sender_id,omitempty"`
	RecipientCount int       `json:"recipient_count"`
	CreatedAt      time.Time `json:"created_at"`
}

// Redirect 表示网址重定向。
type Redirect struct {
	ID          int64  `json:"id"`
	OldPath     string `json:"old_path"`
	NewPath     string `json:"new_path"`
	IsPermanent bool   `json:"is_permanent"`
}

// Embed 表示外链解析缓存（如 B 站短链）。
type Embed struct {
	ID          int64      `json:"id"`
	URL         string     `json:"url"`
	BVID        string     `json:"bvid"`
	ResolvedURL string     `json:"resolved_url"`
	CreatedAt   time.Time  `json:"created_at"`
	ExpiresAt   *time.Time `json:"expires_at,omitempty"`
}
