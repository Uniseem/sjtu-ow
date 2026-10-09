package comments

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func joinInts(ids []int64, sep string) string {
	strs := make([]string, len(ids))
	for i, id := range ids {
		strs[i] = strconv.FormatInt(id, 10)
	}
	return strings.Join(strs, sep)
}

// Store 提供评论域的数据持久化操作。
type Store struct {
	d *db.DB
}

// NewStore 创建评论域存储。
func NewStore(d *db.DB) *Store {
	return &Store{d: d}
}

const commentColumns = `
	c.id, c.article_id, c.user_id, IFNULL(u.nickname, '已注销用户') as author_name,
	c.parent_id, c.reply_to_user_id, IFNULL(ru.nickname, '') as reply_to_user_name,
	c.content, c.is_pinned, c.is_hidden, c.is_deleted, c.like_count, c.version,
	c.created_at, c.updated_at
`

func scanComment(row interface{ Scan(...any) error }) (*Comment, error) {
	var c Comment
	var uid, pid, ruid sql.NullInt64
	var pin, hide, del int
	var created, updated string

	err := row.Scan(
		&c.ID, &c.ArticleID, &uid, &c.AuthorName,
		&pid, &ruid, &c.ReplyToUserName,
		&c.Content, &pin, &hide, &del, &c.LikeCount, &c.Version,
		&created, &updated,
	)
	if err != nil {
		return nil, err
	}

	if uid.Valid {
		c.UserID = &uid.Int64
	}
	if pid.Valid {
		c.ParentID = &pid.Int64
	}
	if ruid.Valid {
		c.ReplyToUserID = &ruid.Int64
	}
	c.IsPinned = pin == 1
	c.IsHidden = hide == 1
	c.IsDeleted = del == 1
	if c.IsDeleted {
		c.Content = "[该评论已删除]"
	}
	c.CreatedAt, _ = db.ParseUTC(created)
	c.UpdatedAt, _ = db.ParseUTC(updated)
	return &c, nil
}

// GetCommentByID 读单条评论。
func (s *Store) GetCommentByID(ctx context.Context, id int64) (*Comment, error) {
	query := `
		SELECT ` + commentColumns + `
		FROM comments c
		LEFT JOIN users u ON u.id = c.user_id
		LEFT JOIN users ru ON ru.id = c.reply_to_user_id
		WHERE c.id = ?
	`
	c, err := scanComment(s.d.ReadPool().QueryRowContext(ctx, query, id))
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return c, nil
}

// ListRootComments 查询顶层评论（规则 182、183）。
func (s *Store) ListRootComments(ctx context.Context, articleID int64, viewerID int64, isMod bool, sortBy string, limit, offset int) ([]*Comment, int, error) {
	where := "WHERE c.article_id = ? AND c.parent_id IS NULL"
	if !isMod {
		// 普通人只见未隐藏且（未删除或有存活子回复）的项
		where += ` AND (
			(c.is_hidden = 0 AND c.is_deleted = 0) OR
			EXISTS (SELECT 1 FROM comments r WHERE r.parent_id = c.id AND r.is_hidden = 0 AND r.is_deleted = 0)
		)`
	}

	countQuery := `SELECT COUNT(*) FROM comments c ` + where
	var total int
	if err := s.d.ReadPool().QueryRowContext(ctx, countQuery, articleID).Scan(&total); err != nil {
		return nil, 0, err
	}

	// 排序：new (置顶 > 时间倒序) 或 top (置顶 > 赞数 > 回复数 > 时间)
	orderClause := "ORDER BY c.is_pinned DESC, c.id DESC"
	if sortBy == "top" {
		orderClause = `
			ORDER BY c.is_pinned DESC, c.like_count DESC,
			(SELECT COUNT(*) FROM comments sub WHERE sub.parent_id = c.id) DESC,
			c.id DESC
		`
	}

	query := `
		SELECT ` + commentColumns + `
		FROM comments c
		LEFT JOIN users u ON u.id = c.user_id
		LEFT JOIN users ru ON ru.id = c.reply_to_user_id
		` + where + `
		` + orderClause + `
		LIMIT ? OFFSET ?
	`
	rows, err := s.d.ReadPool().QueryContext(ctx, query, articleID, limit, offset)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var list []*Comment
	for rows.Next() {
		c, err := scanComment(rows)
		if err != nil {
			return nil, 0, err
		}
		// 规则 182：被删除/隐藏但有回复的显示墓碑占位
		if !isMod && (c.IsDeleted || c.IsHidden) {
			c.IsTombstone = true
			if c.IsDeleted {
				c.Content = "[该评论已删除]"
			} else {
				c.Content = "[该评论已隐藏]"
			}
		}
		list = append(list, c)
	}

	return list, total, nil
}

// ListRepliesForRoots 批量查询一组顶层评论的直接回复（按时间正序）。
func (s *Store) ListRepliesForRoots(ctx context.Context, rootIDs []int64, viewerID int64, isMod bool) (map[int64][]*Comment, error) {
	res := make(map[int64][]*Comment)
	if len(rootIDs) == 0 {
		return res, nil
	}

	inClauses := make([]string, len(rootIDs))
	args := make([]any, len(rootIDs))
	for i, id := range rootIDs {
		inClauses[i] = "?"
		args = append(args[:i], id)
	}

	where := fmt.Sprintf("WHERE c.parent_id IN (%s)", joinInts(rootIDs, ","))
	if !isMod {
		where += " AND c.is_hidden = 0 AND c.is_deleted = 0"
	}

	query := `
		SELECT ` + commentColumns + `
		FROM comments c
		LEFT JOIN users u ON u.id = c.user_id
		LEFT JOIN users ru ON ru.id = c.reply_to_user_id
		` + where + `
		ORDER BY c.id ASC
	`

	rows, err := s.d.ReadPool().QueryContext(ctx, query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		c, err := scanComment(rows)
		if err != nil {
			return nil, err
		}
		if c.ParentID != nil {
			pid := *c.ParentID
			res[pid] = append(res[pid], c)
		}
	}

	return res, nil
}

// CheckMyLikes 查当前用户对列出评论的点赞情况。
func (s *Store) CheckMyLikes(ctx context.Context, commentIDs []int64, userID int64) (map[int64]bool, error) {
	res := make(map[int64]bool)
	if len(commentIDs) == 0 || userID <= 0 {
		return res, nil
	}

	query := fmt.Sprintf(`SELECT comment_id FROM comment_likes WHERE user_id = ? AND comment_id IN (%s)`, joinInts(commentIDs, ","))
	rows, err := s.d.ReadPool().QueryContext(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var cid int64
		if err := rows.Scan(&cid); err == nil {
			res[cid] = true
		}
	}
	return res, nil
}

// CreateComment 插入新评论（规则 173–175）。
func (s *Store) CreateComment(ctx context.Context, c *Comment) error {
	now := time.Now().UTC().Format(time.RFC3339Nano)
	return s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `
			INSERT INTO comments (article_id, user_id, parent_id, reply_to_user_id, content,
				is_pinned, is_hidden, is_deleted, like_count, version, created_at, updated_at)
			VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 1, ?, ?)
		`, c.ArticleID, c.UserID, c.ParentID, c.ReplyToUserID, c.Content, now, now)
		if err != nil {
			return err
		}
		id, err := res.LastInsertId()
		if err != nil {
			return err
		}
		c.ID = id
		c.Version = 1
		c.CreatedAt, _ = db.ParseUTC(now)
		c.UpdatedAt = c.CreatedAt
		return nil
	})
}

// UpdateCommentContent 作者修改正文（规则 177）。
func (s *Store) UpdateCommentContent(ctx context.Context, id int64, newContent string, authorID int64) error {
	now := time.Now().UTC().Format(time.RFC3339Nano)
	return s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `
			UPDATE comments
			SET content = ?, version = version + 1, updated_at = ?
			WHERE id = ? AND user_id = ? AND is_deleted = 0 AND is_hidden = 0
		`, newContent, now, id, authorID)
		if err != nil {
			return err
		}
		affected, _ := res.RowsAffected()
		if affected == 0 {
			return api.Invalid("评论无法编辑或已被隐藏/删除")
		}
		return nil
	})
}

// SoftDeleteComment 作者软删除评论（规则 178：is_deleted=1, 清空正文, 取消置顶）。
func (s *Store) SoftDeleteComment(ctx context.Context, id int64, authorID int64) error {
	now := time.Now().UTC().Format(time.RFC3339Nano)
	return s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `
			UPDATE comments
			SET is_deleted = 1, content = '', is_pinned = 0, version = version + 1, updated_at = ?
			WHERE id = ? AND user_id = ? AND is_hidden = 0 AND is_deleted = 0
		`, now, id, authorID)
		if err != nil {
			return err
		}
		affected, _ := res.RowsAffected()
		if affected == 0 {
			return api.Invalid("评论不存在、已删除或已被管理员隐藏")
		}
		return nil
	})
}

// SetCommentHidden 管理员隐藏/取消隐藏（规则 179：隐藏同时取消置顶）。
func (s *Store) SetCommentHidden(ctx context.Context, id int64, hidden bool) error {
	now := time.Now().UTC().Format(time.RFC3339Nano)
	hideVal := 0
	if hidden {
		hideVal = 1
	}

	return s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		query := `UPDATE comments SET is_hidden = ?, is_pinned = 0, version = version + 1, updated_at = ? WHERE id = ?`
		if !hidden {
			query = `UPDATE comments SET is_hidden = ?, version = version + 1, updated_at = ? WHERE id = ?`
		}
		res, err := tx.ExecContext(txCtx, query, hideVal, now, id)
		if err != nil {
			return err
		}
		affected, _ := res.RowsAffected()
		if affected == 0 {
			return api.NotFound("评论不存在")
		}
		return nil
	})
}

// SetCommentPinned 管理员置顶/取消置顶（规则 179–180：只能置顶顶层、未隐藏、未删除的评论；每篇最多一条置顶）。
func (s *Store) SetCommentPinned(ctx context.Context, articleID int64, commentID int64, pinned bool) error {
	now := time.Now().UTC().Format(time.RFC3339Nano)
	return s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		// 先释放该文章旧的置顶
		if _, err := tx.ExecContext(txCtx, `UPDATE comments SET is_pinned = 0 WHERE article_id = ? AND is_pinned = 1`, articleID); err != nil {
			return err
		}

		if pinned {
			// 校验条件：顶层、未隐藏、未删除
			res, err := tx.ExecContext(txCtx, `
				UPDATE comments
				SET is_pinned = 1, version = version + 1, updated_at = ?
				WHERE id = ? AND article_id = ? AND parent_id IS NULL AND is_hidden = 0 AND is_deleted = 0
			`, now, commentID, articleID)
			if err != nil {
				return err
			}
			affected, _ := res.RowsAffected()
			if affected == 0 {
				return api.Invalid("只能置顶未隐藏、未删除的顶层评论")
			}
		}
		return nil
	})
}

// ToggleLike 原子切换点赞状态（规则 181：赞数不落负）。
func (s *Store) ToggleLike(ctx context.Context, commentID int64, userID int64) (bool, int, error) {
	now := time.Now().UTC().Format(time.RFC3339Nano)
	var isLiked bool
	var count int

	err := s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		// 检查评论是否存在且未被隐藏、未被删除
		var visible int
		err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM comments WHERE id = ? AND is_hidden = 0 AND is_deleted = 0`, commentID).Scan(&visible)
		if err != nil {
			return err
		}
		if visible == 0 {
			return api.NotFound("评论不存在或已不可见")
		}

		// 检查是否已赞
		var exists int
		_ = tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM comment_likes WHERE comment_id = ? AND user_id = ?`, commentID, userID).Scan(&exists)

		if exists > 0 {
			// 取消赞
			_, err = tx.ExecContext(txCtx, `DELETE FROM comment_likes WHERE comment_id = ? AND user_id = ?`, commentID, userID)
			if err != nil {
				return err
			}
			_, err = tx.ExecContext(txCtx, `UPDATE comments SET like_count = MAX(0, like_count - 1) WHERE id = ?`, commentID)
			if err != nil {
				return err
			}
			isLiked = false
		} else {
			// 增加赞
			_, err = tx.ExecContext(txCtx, `INSERT INTO comment_likes (comment_id, user_id, created_at) VALUES (?, ?, ?)`, commentID, userID, now)
			if err != nil {
				return err
			}
			_, err = tx.ExecContext(txCtx, `UPDATE comments SET like_count = like_count + 1 WHERE id = ?`, commentID)
			if err != nil {
				return err
			}
			isLiked = true
		}

		return tx.QueryRowContext(txCtx, `SELECT like_count FROM comments WHERE id = ?`, commentID).Scan(&count)
	})

	if err != nil {
		return false, 0, err
	}
	return isLiked, count, nil
}
