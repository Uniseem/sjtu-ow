package comments

import (
	"time"
)

// Comment 表示评论数据实体。
type Comment struct {
	ID              int64      `json:"id"`
	ArticleID       int64      `json:"article_id"`
	UserID          *int64     `json:"user_id,omitempty"`
	AuthorName      string     `json:"author_name"`
	ParentID        *int64     `json:"parent_id,omitempty"`
	ReplyToUserID   *int64     `json:"reply_to_user_id,omitempty"`
	ReplyToUserName string     `json:"reply_to_user_name,omitempty"`
	Content         string     `json:"content"`
	IsPinned        bool       `json:"is_pinned"`
	IsHidden        bool       `json:"is_hidden"`
	IsDeleted       bool       `json:"is_deleted"`
	IsTombstone     bool       `json:"is_tombstone,omitempty"` // 仅占位（被删但有子回复，规则 182）
	LikeCount       int        `json:"like_count"`
	LikedByMe       bool       `json:"liked_by_me,omitempty"`
	ReplyCount      int        `json:"reply_count,omitempty"`
	Replies         []*Comment `json:"replies,omitempty"`
	Version         int64      `json:"version"`
	CreatedAt       time.Time  `json:"created_at"`
	UpdatedAt       time.Time  `json:"updated_at"`
	EditedAt        *time.Time `json:"edited_at"`
}

// CommentLike 表示用户对评论的点赞记录。
type CommentLike struct {
	CommentID int64     `json:"comment_id"`
	UserID    int64     `json:"user_id"`
	CreatedAt time.Time `json:"created_at"`
}
