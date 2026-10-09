package comments

import (
	"context"
	"database/sql"
	"errors"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// CapCommentsModerate 审核与管理评论的后台能力。
const CapCommentsModerate app.Cap = "comments.moderate"

// Service 协调评论业务规则。
type Service struct {
	store *Store
}

// NewService 创建评论服务。
func NewService(store *Store) *Service {
	return &Service{store: store}
}

// isMod 报当前用户是否具备评论管理权限。
func (s *Service) isMod(v *app.Viewer) bool {
	if v == nil || v.Disabled || v.ID <= 0 {
		return false
	}
	return v.Superuser || v.HasCap(CapCommentsModerate)
}

// checkArticleAvailable 校验文章是否处于公开可评论状态（规则 171–172）。
func (s *Service) checkArticleAvailable(ctx context.Context, articleID int64, mustCommentsOpen bool) error {
	var live, commentsEnabled int
	var expireAt sql.NullString
	err := s.store.d.ReadPool().QueryRowContext(ctx, `
		SELECT p.live, p.expire_at, a.comments_enabled
		FROM pages p
		JOIN articles a ON a.page_id = p.id
		WHERE p.id = ? AND p.kind = 'article'
	`, articleID).Scan(&live, &expireAt, &commentsEnabled)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return api.NotFound("文章不存在")
		}
		return err
	}

	if live != 1 {
		return api.Invalid("文章未发布，无法评论")
	}

	if expireAt.Valid && expireAt.String != "" {
		// 已过期
		t, err := timeFromUTC(expireAt.String)
		if err == nil && t.Before(time.Now()) {
			return api.Invalid("文章已过期，无法评论")
		}
	}

	if mustCommentsOpen && commentsEnabled != 1 {
		return api.Invalid("文章已关闭评论")
	}

	return nil
}

// CreateCommentInput 发表评论入参。
type CreateCommentInput struct {
	ArticleID int64  `json:"article_id"`
	ParentID  *int64 `json:"parent_id,omitempty"`
	Content   string `json:"content"`
}

// CreateComment 发表评论（规则 171–176）。
func (s *Service) CreateComment(ctx *app.Ctx, in CreateCommentInput) (*Comment, error) {
	if ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	if !ctx.Viewer.CanUse("article_comment") {
		return nil, api.Forbidden()
	}

	// 规则 175：正文非空、<= 500 字（按 rune 算）
	content := strings.TrimSpace(in.Content)
	if content == "" {
		return nil, api.Invalid("评论内容不能为空")
	}
	if utf8.RuneCountInString(content) > 500 {
		return nil, api.Invalid("评论内容最多 500 字")
	}

	// 规则 171–172：校验文章公开且开启了评论
	if err := s.checkArticleAvailable(ctx.Context, in.ArticleID, true); err != nil {
		return nil, err
	}

	var parentID *int64
	var replyToUserID *int64

	// 规则 174：回复扁平化至一层，并记录被回复者
	if in.ParentID != nil && *in.ParentID > 0 {
		parent, err := s.store.GetCommentByID(ctx.Context, *in.ParentID)
		if err != nil {
			return nil, err
		}
		if parent == nil || parent.ArticleID != in.ArticleID {
			return nil, api.Invalid("所回复的评论不存在")
		}
		if parent.IsDeleted || parent.IsHidden {
			return nil, api.Invalid("所回复的评论已被删除或隐藏，无法回复")
		}

		if parent.ParentID != nil {
			// 回复的是楼中楼回复：扁平化到顶层父评论
			parentID = parent.ParentID
			replyToUserID = parent.UserID
		} else {
			// 回复的是顶层评论
			pid := parent.ID
			parentID = &pid
			replyToUserID = parent.UserID
		}
	}

	authorID := ctx.Viewer.ID
	c := &Comment{
		ArticleID:     in.ArticleID,
		UserID:        &authorID,
		ParentID:      parentID,
		ReplyToUserID: replyToUserID,
		Content:       content,
	}

	if err := s.store.CreateComment(ctx.Context, c); err != nil {
		return nil, err
	}

	return s.store.GetCommentByID(ctx.Context, c.ID)
}

// EditCommentInput 修改评论入参。
type EditCommentInput struct {
	Content string `json:"content"`
}

// EditComment 作者修改评论（规则 175, 177）。
func (s *Service) EditComment(ctx *app.Ctx, id int64, in EditCommentInput) (*Comment, error) {
	if ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	if !ctx.Viewer.CanUse("article_comment") {
		return nil, api.Forbidden()
	}

	content := strings.TrimSpace(in.Content)
	if content == "" {
		return nil, api.Invalid("评论内容不能为空")
	}
	if utf8.RuneCountInString(content) > 500 {
		return nil, api.Invalid("评论内容最多 500 字")
	}

	comment, err := s.store.GetCommentByID(ctx.Context, id)
	if err != nil {
		return nil, err
	}
	if comment == nil {
		return nil, api.NotFound("评论不存在")
	}
	if comment.UserID == nil || *comment.UserID != ctx.Viewer.ID {
		return nil, api.Forbidden()
	}

	// 规则 177：文章关闭评论后作者不能改旧评论
	if err := s.checkArticleAvailable(ctx.Context, comment.ArticleID, true); err != nil {
		return nil, err
	}

	if err := s.store.UpdateCommentContent(ctx.Context, id, content, ctx.Viewer.ID); err != nil {
		return nil, err
	}

	return s.store.GetCommentByID(ctx.Context, id)
}

// DeleteComment 作者软删除评论（规则 178）。
func (s *Service) DeleteComment(ctx *app.Ctx, id int64) error {
	if ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return api.Unauthorized("要先登录")
	}

	comment, err := s.store.GetCommentByID(ctx.Context, id)
	if err != nil {
		return err
	}
	if comment == nil {
		return api.NotFound("评论不存在")
	}
	if comment.UserID == nil || *comment.UserID != ctx.Viewer.ID {
		return api.Forbidden()
	}
	if comment.IsHidden {
		return api.Invalid("评论已被管理员隐藏，作者无法删除")
	}

	return s.store.SoftDeleteComment(ctx.Context, id, ctx.Viewer.ID)
}

// SetHidden 管理员隐藏/取消隐藏（规则 179）。
func (s *Service) SetHidden(ctx *app.Ctx, id int64, hidden bool) error {
	if !s.isMod(ctx.Viewer) {
		return api.Forbidden()
	}
	return s.store.SetCommentHidden(ctx.Context, id, hidden)
}

// SetPinned 管理员置顶/取消置顶（规则 179–180）。
func (s *Service) SetPinned(ctx *app.Ctx, articleID int64, commentID int64, pinned bool) error {
	if !s.isMod(ctx.Viewer) {
		return api.Forbidden()
	}
	return s.store.SetCommentPinned(ctx.Context, articleID, commentID, pinned)
}

// ToggleLike 点赞/取消点赞（规则 181）。
func (s *Service) ToggleLike(ctx *app.Ctx, commentID int64) (bool, int, error) {
	if ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return false, 0, api.Unauthorized("要先登录")
	}
	return s.store.ToggleLike(ctx.Context, commentID, ctx.Viewer.ID)
}

// ListCommentsInput 查询列表入参。
type ListCommentsInput struct {
	SortBy   string `json:"sort"` // "new" 或 "top"
	Page     int    `json:"page"`
	PageSize int    `json:"page_size"`
}

// ListCommentsResult 评论列表结果。
type ListCommentsResult struct {
	Total    int        `json:"total"`
	Page     int        `json:"page"`
	PageSize int        `json:"page_size"`
	Comments []*Comment `json:"comments"`
}

// ListComments 查询文章评论列表（规则 182–183）。
func (s *Service) ListComments(ctx *app.Ctx, articleID int64, in ListCommentsInput) (*ListCommentsResult, error) {
	// 检查文章是否存在
	if err := s.checkArticleAvailable(ctx.Context, articleID, false); err != nil {
		return nil, err
	}

	page := in.Page
	if page < 1 {
		page = 1
	}
	pageSize := in.PageSize
	if pageSize < 1 || pageSize > 50 {
		pageSize = 20
	}
	offset := (page - 1) * pageSize

	sortBy := in.SortBy
	if sortBy != "top" {
		sortBy = "new"
	}

	var viewerID int64
	if ctx.Viewer != nil {
		viewerID = ctx.Viewer.ID
	}
	isMod := s.isMod(ctx.Viewer)

	// 1. 查询顶层评论
	roots, total, err := s.store.ListRootComments(ctx.Context, articleID, viewerID, isMod, sortBy, pageSize, offset)
	if err != nil {
		return nil, err
	}

	// 2. 批量查回复
	rootIDs := make([]int64, len(roots))
	for i, r := range roots {
		rootIDs[i] = r.ID
	}
	repliesMap, err := s.store.ListRepliesForRoots(ctx.Context, rootIDs, viewerID, isMod)
	if err != nil {
		return nil, err
	}

	// 3. 批量查当前用户的点赞
	allIDs := append([]int64{}, rootIDs...)
	for _, reps := range repliesMap {
		for _, rep := range reps {
			allIDs = append(allIDs, rep.ID)
		}
	}
	myLikes, _ := s.store.CheckMyLikes(ctx.Context, allIDs, viewerID)

	for _, r := range roots {
		r.LikedByMe = myLikes[r.ID]
		reps := repliesMap[r.ID]
		r.ReplyCount = len(reps)
		for _, rep := range reps {
			rep.LikedByMe = myLikes[rep.ID]
		}
		r.Replies = reps
	}

	return &ListCommentsResult{
		Total:    total,
		Page:     page,
		PageSize: pageSize,
		Comments: roots,
	}, nil
}

func timeFromUTC(s string) (time.Time, error) {
	return time.Parse(time.RFC3339Nano, s)
}
