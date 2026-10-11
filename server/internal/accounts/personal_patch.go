package accounts

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type GameChanges struct {
	Battletag   *string `json:"battletag,omitempty"`
	RankTank    *int    `json:"rank_tank,omitempty"`
	RankDamage  *int    `json:"rank_damage,omitempty"`
	RankSupport *int    `json:"rank_support,omitempty"`
	present     map[string]bool
}

// Preserve the distinction between an omitted rank and an explicit null.
// Exported field types remain ordinary nullable integers for apigen.
func (ch *GameChanges) UnmarshalJSON(raw []byte) error {
	type plain GameChanges
	var value plain
	if err := json.Unmarshal(raw, &value); err != nil {
		return err
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(raw, &fields); err != nil {
		return err
	}
	value.present = map[string]bool{}
	for field := range fields {
		switch field {
		case "battletag", "rank_tank", "rank_damage", "rank_support":
			value.present[field] = true
		default:
			return fmt.Errorf("不支持修改字段 %s", field)
		}
	}
	*ch = GameChanges(value)
	return nil
}

type GameValues struct {
	Battletag   string `json:"battletag"`
	RankTank    *int   `json:"rank_tank"`
	RankDamage  *int   `json:"rank_damage"`
	RankSupport *int   `json:"rank_support"`
}

type GameCurrent struct {
	Version int64      `json:"version"`
	Values  GameValues `json:"values"`
}

func gameValues(ga *GameAccount) GameValues {
	return GameValues{
		Battletag:   ga.Battletag,
		RankTank:    ga.RankTank,
		RankDamage:  ga.RankDamage,
		RankSupport: ga.RankSupport,
	}
}

func sameRank(a, b *int) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

func (s *Service) patchActor(ctx *app.Ctx, txCtx context.Context, tx *db.Tx) error {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return api.Unauthorized("要先登录")
	}
	u, err := s.store.GetByIDTx(txCtx, tx, ctx.Viewer.ID)
	if err != nil {
		return err
	}
	if u == nil || !u.IsActive {
		return api.Unauthorized("账号不存在或已停用")
	}
	return nil
}

func (s *Service) patchGame(ctx *app.Ctx, in UpdateGameAccountInput) (*GameAccountResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	if in.BaseVersion == nil || *in.BaseVersion < 0 {
		return nil, api.Invalid("请提供游戏 ID 版本。")
	}
	var out *GameAccountResult
	now := s.clock.Now().UTC()
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		if err := s.patchActor(ctx, txCtx, tx); err != nil {
			return err
		}
		ga, err := scanGameAccount(tx.QueryRowContext(txCtx,
			`SELECT `+gameAccountCols+` FROM game_accounts WHERE id=? AND user_id=?`, int64(in.ID), ctx.Viewer.ID))
		if err != nil {
			return err
		}
		if ga == nil {
			return api.NotFound("游戏 ID 不存在")
		}
		if ga.Version != *in.BaseVersion {
			return api.Stale(GameCurrent{Version: ga.Version, Values: gameValues(ga)})
		}
		result := toGameAccountResult(*ga)
		out = &result
		out.Fields = map[string][]string{}
		out.SavedAt = now
		ch := in.Changes
		if ch.Battletag != nil {
			tag := strings.TrimSpace(*ch.Battletag)
			if err := ValidateBattletag(tag); err != nil {
				out.Fields["battletag"] = []string{err.Error()}
			} else {
				var used int
				if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM game_accounts WHERE battletag_norm=? AND id<>?`, NormalizeBattletag(tag), ga.ID).Scan(&used); err != nil {
					return err
				}
				if used > 0 {
					out.Fields["battletag"] = []string{"该游戏 ID 已被其他账号绑定，如有疑问请联系管理员"}
				} else {
					ga.Battletag, ga.BattletagNorm = tag, NormalizeBattletag(tag)
					out.Saved = append(out.Saved, "battletag")
				}
			}
		}
		ranks := []struct {
			name    string
			value   *int
			current **int
		}{
			{"rank_tank", ch.RankTank, &ga.RankTank},
			{"rank_damage", ch.RankDamage, &ga.RankDamage},
			{"rank_support", ch.RankSupport, &ga.RankSupport},
		}
		changedRanks := false
		for _, rank := range ranks {
			provided := ch.present[rank.name] || rank.value != nil
			if !provided {
				continue
			}
			if rank.value != nil && (*rank.value < 0 || *rank.value > Top500Score) {
				out.Fields[rank.name] = []string{"非法段位分数"}
				continue
			}
			changedRanks = changedRanks || !sameRank(*rank.current, rank.value)
			*rank.current = rank.value
			out.Saved = append(out.Saved, rank.name)
		}
		if changedRanks {
			ga.RanksUpdatedAt = now
		}
		if len(out.Saved) > 0 {
			_, err := tx.ExecContext(txCtx, `UPDATE game_accounts SET
				battletag=?,battletag_norm=?,rank_tank=?,rank_damage=?,rank_support=?,
				ranks_updated_at=?,updated_at=?,version=version+1 WHERE id=? AND user_id=? AND version=?`,
				ga.Battletag, ga.BattletagNorm, ga.RankTank, ga.RankDamage, ga.RankSupport,
				db.FormatUTC(ga.RanksUpdatedAt), db.FormatUTC(now), ga.ID, ga.UserID, ga.Version)
			if err != nil {
				return err
			}
			ga.Version++
		}
		out.Version = ga.Version
		values := gameValues(ga)
		out.Values = &values
		out.Battletag = ga.Battletag
		out.RankTank, out.RankDamage, out.RankSupport = ga.RankTank, ga.RankDamage, ga.RankSupport
		out.TankLabel, out.DamageLabel, out.SupportLabel = FormatRank(ga.RankTank), FormatRank(ga.RankDamage), FormatRank(ga.RankSupport)
		out.RanksUpdatedAt = ga.RanksUpdatedAt
		return nil
	})
	if err != nil {
		return nil, err
	}
	return out, nil
}

type ContactChanges struct {
	Type  *string `json:"type,omitempty"`
	Value *string `json:"value,omitempty"`
}

type ContactValues struct {
	Type  string `json:"type"`
	Value string `json:"value"`
}

type ContactCurrent struct {
	Version int64         `json:"version"`
	Values  ContactValues `json:"values"`
}

type UpdateContactInput struct {
	ID          api.ID         `path:"id"`
	BaseVersion int64          `json:"base_version"`
	Changes     ContactChanges `json:"changes"`
}

func (s *Service) UpdateContact(ctx *app.Ctx, in UpdateContactInput) (*ContactResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	if in.BaseVersion < 0 {
		return nil, api.Invalid("请提供联系方式版本。")
	}
	now := s.clock.Now().UTC()
	var out *ContactResult
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		if err := s.patchActor(ctx, txCtx, tx); err != nil {
			return err
		}
		contact, err := scanContact(tx.QueryRowContext(txCtx,
			`SELECT `+contactCols+` FROM contacts WHERE id=? AND user_id=?`, int64(in.ID), ctx.Viewer.ID))
		if err != nil {
			return err
		}
		if contact == nil {
			return api.NotFound("联系方式不存在")
		}
		old := ContactValues{Type: contact.Type, Value: contact.Value}
		if contact.Version != in.BaseVersion {
			return api.Stale(ContactCurrent{Version: contact.Version, Values: old})
		}
		result := toContactResult(*contact)
		out = &result
		out.Fields = map[string][]string{}
		out.SavedAt = now
		values := old
		if in.Changes.Type != nil {
			values.Type = strings.TrimSpace(*in.Changes.Type)
		}
		if in.Changes.Value != nil {
			values.Value = strings.TrimSpace(*in.Changes.Value)
		}
		if err := ValidateContact(values.Type, values.Value); err != nil {
			out.Fields["value"] = []string{err.Error()}
		} else {
			var duplicates int
			if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM contacts WHERE user_id=? AND type=? AND id<>?`, contact.UserID, values.Type, contact.ID).Scan(&duplicates); err != nil {
				return err
			}
			if duplicates > 0 {
				out.Fields["type"] = []string{"每种联系方式只能填写一次。"}
			}
		}
		if len(out.Fields) == 0 && (in.Changes.Type != nil || in.Changes.Value != nil) {
			if _, err := tx.ExecContext(txCtx, `UPDATE contacts SET type=?,value=?,updated_at=?,version=version+1 WHERE id=? AND user_id=? AND version=?`,
				values.Type, values.Value, db.FormatUTC(now), contact.ID, contact.UserID, contact.Version); err != nil {
				return err
			}
			contact.Type, contact.Value = values.Type, values.Value
			contact.Version++
			if in.Changes.Type != nil {
				out.Saved = append(out.Saved, "type")
			}
			if in.Changes.Value != nil {
				out.Saved = append(out.Saved, "value")
			}
		} else {
			values = old
		}
		out.Version = contact.Version
		out.Type, out.Value, out.TypeLabel = contact.Type, contact.Value, AllContactTypes[contact.Type]
		out.Values = &values
		return nil
	})
	if err != nil {
		return nil, err
	}
	return out, nil
}
