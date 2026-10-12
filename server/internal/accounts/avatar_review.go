package accounts

import (
	"context"
	"database/sql"
	"errors"
	"strings"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
)

var avatarReasons = map[string]string{
	"illegal": "违法违规", "porn": "色情低俗", "attack": "人身攻击",
	"politics": "政治敏感", "scam": "广告与诈骗", "game_trade": "游戏违规交易",
	"privacy": "泄露他人隐私", "impersonation": "冒充官方", "other": "其他可疑",
}

func avatarReasonLabel(reason string) string { return avatarReasons[reason] }

// ReviewAvatar atomically retires only the approved upload currently in use,
// records the reviewer and freezes the exact owner notification.
func (s *Service) ReviewAvatar(ctx *app.Ctx, submissionID int64, reason, note string) error {
	if ctx == nil || ctx.Viewer == nil || !ctx.Viewer.HasCap(CapModerationReview) {
		return api.Forbidden()
	}
	if avatarReasonLabel(reason) == "" {
		return api.InvalidFields(map[string][]string{"reason": {"请选一个原因。"}})
	}
	if utf8.RuneCountInString(note) > 200 {
		return api.InvalidFields(map[string][]string{"note": {"说明最多200字。"}})
	}
	if s.media == nil {
		return api.NewErr(503, "unavailable", "头像处理暂时不可用。")
	}
	now := ctx.Now().UTC()
	var imageID int64
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		var userID int64
		var image, current sql.NullInt64
		var status, email, nickname string
		err := tx.QueryRowContext(txCtx, `SELECT a.user_id,a.image_id,a.status,u.avatar_image_id,u.email,u.nickname
		FROM avatar_submissions a JOIN users u ON u.id=a.user_id WHERE a.id=?`, submissionID).
			Scan(&userID, &image, &status, &current, &email, &nickname)
		if errors.Is(err, sql.ErrNoRows) {
			return api.NotFound("头像记录不存在")
		}
		if err != nil {
			return err
		}
		if status != "approved" {
			return api.NewErr(409, "state_changed", "这张头像已经被处理过了，刷新看看。")
		}
		if !image.Valid || !current.Valid || image.Int64 != current.Int64 {
			return api.NewErr(409, "state_changed", "这张头像现在没在用，不用撤下。")
		}
		imageID = image.Int64
		if _, err := tx.ExecContext(txCtx, `UPDATE avatar_submissions SET status='taken_down',reason=?,note=?,handling_note=?,reviewed_by=?,reviewed_at=? WHERE id=?`, reason, note, note, ctx.Viewer.ID, db.FormatUTC(now), submissionID); err != nil {
			return err
		}
		if err := s.store.SetUserAvatar(txCtx, tx, userID, nil, now); err != nil {
			return err
		}
		if _, err := tx.ExecContext(txCtx, `DELETE FROM images WHERE id=?`, imageID); err != nil {
			return err
		}
		facts := [][2]string{{"原因", avatarReasonLabel(reason)}}
		if note != "" {
			facts = append(facts, [2]string{"说明", note})
		}
		letter := mail.Letter{Subject: "你的头像已被撤下", Lead: "你正在用的头像被管理员撤下了，现在显示的是默认头像。", Facts: facts,
			Paragraphs: []string{"那张图已经删除。你可以换一张重新上传。"}, Action: []string{"重新上传", strings.TrimRight(s.siteURL, "/") + "/me/"}, Reason: "你收到这封邮件，是因为你在社区上传过头像。"}
		if _, err := outbox.Send(txCtx, tx, ctx.Letters, s.siteURL, letter, []mail.Person{{Address: email, Name: nickname}}, now); err != nil {
			return err
		}
		return audit.Record(txCtx, tx, ctx.Viewer.ID, "avatar.take_down", "avatar_submission", submissionID, map[string]any{"reason": reason, "note": note}, now)
	})
	if err != nil {
		return err
	}
	s.media.DeleteImageFiles(imageID)
	return nil
}

func (s *Store) AvatarReviewCounts(ctx context.Context) (map[string]int, error) {
	out := map[string]int{"approved": 0, "taken_down": 0, "rejected": 0}
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT status,COUNT(*) FROM avatar_submissions WHERE status IN ('approved','taken_down','rejected') GROUP BY status`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var status string
		var count int
		if err := rows.Scan(&status, &count); err != nil {
			return nil, err
		}
		out[status] = count
	}
	return out, rows.Err()
}
