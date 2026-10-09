package comments

import (
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

// Module 负责评论域路由注册与调度。
type Module struct {
	svc *Service
}

// NewModule 创建评论模块。
func NewModule(svc *Service) *Module {
	return &Module{svc: svc}
}

// ListCommentsIn 是 GET /api/articles/{id}/comments 的入参。
type ListCommentsIn struct {
	ID       api.ID `path:"id"`
	Sort     string `query:"sort"`
	Page     int    `query:"page"`
	PageSize int    `query:"page_size"`
}

// ListCommentsOut 是 GET /api/articles/{id}/comments 的出参。
type ListCommentsOut = ListCommentsResult

// PostCommentIn 是 POST /api/articles/{id}/comments 的入参。
type PostCommentIn struct {
	ID       api.ID `path:"id"`
	ParentID *int64 `json:"parent_id,omitempty"`
	Content  string `json:"content"`
}

// PostCommentOut 是 POST /api/articles/{id}/comments 的出参。
type PostCommentOut struct {
	Comment *Comment `json:"comment"`
}

// PatchCommentIn 是 PATCH /api/comments/{id} 的入参。
type PatchCommentIn struct {
	ID      api.ID `path:"id"`
	Content string `json:"content"`
}

// PatchCommentOut 是 PATCH /api/comments/{id} 的出参。
type PatchCommentOut struct {
	Comment *Comment `json:"comment"`
}

// DeleteCommentIn 是 DELETE /api/comments/{id} 的入参。
type DeleteCommentIn struct {
	ID api.ID `path:"id"`
}

// DeleteCommentOut 是 DELETE /api/comments/{id} 的出参。
type DeleteCommentOut struct {
	Result string `json:"result"`
}

// LikeCommentIn 是 POST /api/comments/{id}/like 的入参。
type LikeCommentIn struct {
	ID api.ID `path:"id"`
}

// LikeCommentOut 是 POST /api/comments/{id}/like 的出参。
type LikeCommentOut struct {
	Liked     bool `json:"liked"`
	LikeCount int  `json:"like_count"`
}

// HideCommentIn 是 POST /api/comments/{id}/hide 的入参。
type HideCommentIn struct {
	ID     api.ID `path:"id"`
	Hidden bool   `json:"hidden"`
}

// HideCommentOut 是 POST /api/comments/{id}/hide 的出参。
type HideCommentOut struct {
	Result string `json:"result"`
}

// PinCommentIn 是 POST /api/comments/{id}/pin 的入参。
type PinCommentIn struct {
	ID        api.ID `path:"id"`
	ArticleID int64  `json:"article_id"`
	Pinned    bool   `json:"pinned"`
}

// PinCommentOut 是 POST /api/comments/{id}/pin 的出参。
type PinCommentOut struct {
	Result string `json:"result"`
}

// AdminListCommentsIn 是 GET /api/admin/comments 的入参。
type AdminListCommentsIn struct {
	Q        string `query:"q"`
	Hidden   *bool  `query:"hidden"`
	Pinned   *bool  `query:"pinned"`
	Page     int    `query:"page"`
	PageSize int    `query:"page_size"`
}

// AdminListCommentsOut 是 GET /api/admin/comments 的出参。
type AdminListCommentsOut struct {
	Items    []AdminCommentRow `json:"items"`
	Total    int               `json:"total"`
	Page     int               `json:"page"`
	PageSize int               `json:"page_size"`
}

// Routes 注册评论域所有路由接口。
func (m *Module) Routes(r *api.Registry) {
	// 公开读取列表
	api.Get(r, "/api/articles/{id}/comments", api.Public, m.listComments)

	// 会员发表与修改
	api.Post(r, "/api/articles/{id}/comments", api.Member, m.postComment,
		api.Limit(ratelimit.CommentCreateMinute, ratelimit.CommentCreateDaily))
	api.Patch(r, "/api/comments/{id}", api.Member, m.patchComment,
		api.Limit(ratelimit.CommentCreateMinute))
	api.Delete(r, "/api/comments/{id}", api.Member, m.deleteComment,
		api.NoLimit("删除评论无需限流"))

	// 点赞
	api.Post(r, "/api/comments/{id}/like", api.Member, m.likeComment,
		api.Limit(ratelimit.CommentVote))

	// 管理员操作
	api.Post(r, "/api/comments/{id}/hide", api.Cap(CapCommentsModerate), m.hideComment,
		api.NoLimit("管理员隐藏评论无需限流"))
	api.Post(r, "/api/comments/{id}/pin", api.Cap(CapCommentsModerate), m.pinComment,
		api.NoLimit("管理员置顶评论无需限流"))
	api.Get(r, "/api/admin/comments", api.Cap(CapCommentsModerate), m.adminListComments,
		api.Nav("review", "comments"))
}

func (m *Module) adminListComments(ctx *app.Ctx, in AdminListCommentsIn) (AdminListCommentsOut, error) {
	items, total, err := m.svc.ListAdminComments(ctx, in.Q, in.Hidden, in.Pinned, in.Page, in.PageSize)
	if err != nil {
		return AdminListCommentsOut{}, err
	}
	page := in.Page
	if page < 1 {
		page = 1
	}
	pageSize := in.PageSize
	if pageSize < 1 {
		pageSize = 50
	}
	return AdminListCommentsOut{
		Items:    items,
		Total:    total,
		Page:     page,
		PageSize: pageSize,
	}, nil
}

func (m *Module) listComments(ctx *app.Ctx, in ListCommentsIn) (ListCommentsOut, error) {
	res, err := m.svc.ListComments(ctx, int64(in.ID), ListCommentsInput{
		SortBy:   in.Sort,
		Page:     in.Page,
		PageSize: in.PageSize,
	})
	if err != nil {
		return ListCommentsOut{}, err
	}
	return *res, nil
}

func (m *Module) postComment(ctx *app.Ctx, in PostCommentIn) (PostCommentOut, error) {
	c, err := m.svc.CreateComment(ctx, CreateCommentInput{
		ArticleID: int64(in.ID),
		ParentID:  in.ParentID,
		Content:   in.Content,
	})
	if err != nil {
		return PostCommentOut{}, err
	}
	return PostCommentOut{Comment: c}, nil
}

func (m *Module) patchComment(ctx *app.Ctx, in PatchCommentIn) (PatchCommentOut, error) {
	c, err := m.svc.EditComment(ctx, int64(in.ID), EditCommentInput{
		Content: in.Content,
	})
	if err != nil {
		return PatchCommentOut{}, err
	}
	return PatchCommentOut{Comment: c}, nil
}

func (m *Module) deleteComment(ctx *app.Ctx, in DeleteCommentIn) (DeleteCommentOut, error) {
	if err := m.svc.DeleteComment(ctx, int64(in.ID)); err != nil {
		return DeleteCommentOut{}, err
	}
	return DeleteCommentOut{Result: "ok"}, nil
}

func (m *Module) likeComment(ctx *app.Ctx, in LikeCommentIn) (LikeCommentOut, error) {
	liked, count, err := m.svc.ToggleLike(ctx, int64(in.ID))
	if err != nil {
		return LikeCommentOut{}, err
	}
	return LikeCommentOut{
		Liked:     liked,
		LikeCount: count,
	}, nil
}

func (m *Module) hideComment(ctx *app.Ctx, in HideCommentIn) (HideCommentOut, error) {
	if err := m.svc.SetHidden(ctx, int64(in.ID), in.Hidden); err != nil {
		return HideCommentOut{}, err
	}
	return HideCommentOut{Result: "ok"}, nil
}

func (m *Module) pinComment(ctx *app.Ctx, in PinCommentIn) (PinCommentOut, error) {
	if err := m.svc.SetPinned(ctx, in.ArticleID, int64(in.ID), in.Pinned); err != nil {
		return PinCommentOut{}, err
	}
	return PinCommentOut{Result: "ok"}, nil
}
