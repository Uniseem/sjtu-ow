package accounts

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
)

type ProfileGap struct {
	Label string `json:"label"`
	Href  string `json:"href"`
	Hint  string `json:"hint"`
}

type AvatarTurnedDown struct {
	Status        string `json:"status"`
	ReasonDisplay string `json:"reason_display"`
	Note          string `json:"note"`
}

// PersonalContext is projected for the owner only. It never carries contact
// contents, mail recipients, credentials or administrator-only settings.
type PersonalContext struct {
	AvatarImageID        *int64            `json:"avatar_image_id"`
	DefaultAvatarImageID *int64            `json:"default_avatar_image_id"`
	AvatarCanUpload      bool              `json:"avatar_can_upload"`
	AvatarDenied         string            `json:"avatar_denied"`
	AvatarTurnedDown     *AvatarTurnedDown `json:"avatar_turned_down"`
	MaxGameAccounts      int               `json:"max_game_accounts"`
	ProfileGaps          []ProfileGap      `json:"profile_gaps"`
	WaitingLetters       int               `json:"waiting_letters"`
	DeletionBlockers     []string          `json:"deletion_blockers"`
}

func (s *Service) personalContext(ctx *app.Ctx, user *User) (PersonalContext, error) {
	out := PersonalContext{
		AvatarImageID:    user.AvatarImageID,
		MaxGameAccounts:  5,
		ProfileGaps:      []ProfileGap{},
		DeletionBlockers: []string{},
	}
	pool, err := media.LoadPool(ctx.Context, s.d.ReadPool(), "default_avatar")
	if err != nil {
		return out, err
	}
	main := user.MainRole
	if main == "" {
		roles := ParseRoles(user.FlexRoles)
		if len(roles) > 0 {
			main = roles[0]
		}
	}
	out.DefaultAvatarImageID = media.PickAvatar(pool, user.ID, main)
	out.AvatarCanUpload = ctx.Viewer != nil && ctx.Viewer.CanUse(FeatureAvatarUpload)
	if !out.AvatarCanUpload {
		out.AvatarDenied = FeatureDeniedMessage
	}
	var games, contacts int
	if err := s.d.ReadPool().QueryRowContext(ctx.Context,
		`SELECT (SELECT COUNT(*) FROM game_accounts WHERE user_id=?),
		(SELECT COUNT(*) FROM contacts WHERE user_id=?)`, user.ID, user.ID).Scan(&games, &contacts); err != nil {
		return out, err
	}
	if games == 0 {
		out.ProfileGaps = append(out.ProfileGaps, ProfileGap{
			Label: "游戏 ID", Href: "/me/game-accounts/", Hint: "至少绑定 1 个游戏 ID",
		})
	}
	if contacts == 0 {
		out.ProfileGaps = append(out.ProfileGaps, ProfileGap{
			Label: "联系方式", Href: "/me/contacts/", Hint: "至少填写 1 种联系方式",
		})
	}
	var state, note string
	err = s.d.ReadPool().QueryRowContext(ctx.Context,
		`SELECT status,handling_note FROM avatar_submissions
		WHERE user_id=? AND status<>'withdrawn' ORDER BY created_at DESC,id DESC LIMIT 1`, user.ID).Scan(&state, &note)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return out, err
	}
	if err == nil && (state == "rejected" || state == "taken_down") {
		out.AvatarTurnedDown = &AvatarTurnedDown{Status: state, ReasonDisplay: note}
	}
	cutoff := db.FormatUTC(s.clock.Now().UTC().Add(-7 * 24 * time.Hour))
	if err := s.d.ReadPool().QueryRowContext(ctx.Context,
		`SELECT COUNT(DISTINCT batch) FROM held_letters WHERE actor_id=? AND state='waiting' AND created_at>=?`,
		user.ID, cutoff).Scan(&out.WaitingLetters); err != nil {
		return out, err
	}
	out.DeletionBlockers, err = s.deletionBlockers(ctx.Context, user.ID)
	return out, err
}

func (s *Service) deletionBlockers(ctx context.Context, userID int64) ([]string, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT t.name FROM team_memberships m
		JOIN teams t ON t.id=m.team_id WHERE m.user_id=? AND m.role='captain'
		AND t.disbanded_at IS NULL ORDER BY t.id`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []string{}
	for rows.Next() {
		var name string
		if err := rows.Scan(&name); err != nil {
			return nil, err
		}
		out = append(out, fmt.Sprintf("你是战队「%s」的队长，请先转让队长或解散战队。", name))
	}
	return out, rows.Err()
}
