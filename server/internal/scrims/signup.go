package scrims

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func (s *Service) canSignup(ctx context.Context, userID int64) (bool, error) {
	if s.viewers == nil {
		return true, nil
	}
	v, err := s.viewers(ctx, userID)
	if err != nil {
		return false, err
	}
	return v != nil && !v.Disabled && v.CanUse(accounts.FeatureScrimSignup), nil
}

// signupProblems 这个人现在为什么不能报名（规则 153）。
func (s *Service) signupProblems(ctx context.Context, q db.DBTX, sc *Scrim, userID int64, now time.Time) ([]string, error) {
	var nick string
	var active, sjtu int
	if err := q.QueryRowContext(ctx, `SELECT nickname, is_active, is_sjtu FROM users WHERE id = ?`, userID).Scan(&nick, &active, &sjtu); err != nil {
		if err == sql.ErrNoRows {
			return []string{"请先登录"}, nil
		}
		return nil, err
	}
	var out []string
	if active != 1 {
		out = append(out, "账号已停用")
	} else if ok, err := s.canSignup(ctx, userID); err != nil {
		return nil, err
	} else if !ok {
		out = append(out, accounts.FeatureDeniedMessage)
	}
	var games, contacts int
	if err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM game_accounts WHERE user_id = ?`, userID).Scan(&games); err != nil {
		return nil, err
	}
	if err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM contacts WHERE user_id = ?`, userID).Scan(&contacts); err != nil {
		return nil, err
	}
	var gaps []string
	if games < 1 {
		gaps = append(gaps, "游戏 ID")
	}
	if contacts < 1 {
		gaps = append(gaps, "联系方式")
	}
	if len(gaps) > 0 {
		out = append(out, fmt.Sprintf("资料不完整（缺少%s）", strings.Join(gaps, "、")))
	}
	if sc.SjtuOnly && sjtu != 1 {
		out = append(out, "这场内战仅限交大用户参加")
	}
	if sc.Status != StatusPublished {
		out = append(out, "这场内战当前不接受报名")
	} else if d := sc.Deadline(); d != nil && now.After(*d) {
		out = append(out, "报名已截止")
	}
	return out, nil
}

// roleProblems 段位规则，规格不同要求不同（规则 155、156）。
func roleProblems(sc *Scrim, acc *Account, roles []string) []string {
	if len(roles) == 0 {
		return []string{"至少要勾选一个能打的位置"}
	}
	if sc.RoleQueue() {
		var missing []string
		for _, r := range roles {
			if acc.Rank(r) == nil {
				missing = append(missing, RoleLabels[r])
			}
		}
		if len(missing) > 0 {
			return []string{fmt.Sprintf("角色限定内战要求勾选的每个位置都填了段位，这个游戏 ID 还缺：%s", strings.Join(missing, "、"))}
		}
		return nil
	}
	for _, r := range RoleOrder {
		if acc.Rank(r) != nil {
			return nil
		}
	}
	return []string{"这个游戏 ID 一个位置的段位都没填"}
}

// SignupInput 是报名的入参。
type SignupInput struct {
	ScrimID       int64
	GameAccountID int64
	Roles         []string
}

func rolesSet(roles []string) (tank, damage, support int) {
	for _, r := range roles {
		switch r {
		case Tank:
			tank = 1
		case Damage:
			damage = 1
		case Support:
			support = 1
		}
	}
	return
}

// markChanged 让管理员看到已保存的分队和报名对不上了（规则 157）。
func markChanged(ctx context.Context, tx *db.Tx, scrimID int64, now time.Time) error {
	_, err := tx.ExecContext(ctx, `UPDATE scrims SET roster_changed_at = ?, board_version = board_version + 1 WHERE id = ?`, db.FormatUTC(now), scrimID)
	return err
}

// SignUp 建立或更新自己的报名（规则 153–157）。改游戏 ID 或改位置会清空已有的分队结果
// （上场标记、队伍、位置、用的分数），并打标记提醒管理员。
func (s *Service) SignUp(ctx *app.Ctx, in SignupInput) (*Signup, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	var out *Signup
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		sc, err := GetScrim(txCtx, tx, in.ScrimID)
		if err != nil {
			return err
		}
		if sc == nil || !sc.IsPublic() {
			return api.NotFound("内战不存在")
		}
		probs, err := s.signupProblems(txCtx, tx, sc, v.ID, now)
		if err != nil {
			return err
		}
		var acc *Account
		if in.GameAccountID > 0 {
			acc, err = loadAccount(txCtx, tx, `SELECT id, battletag, rank_tank, rank_damage, rank_support FROM game_accounts WHERE id = ? AND user_id = ?`, in.GameAccountID, v.ID)
			if err != nil {
				return err
			}
		}
		if acc == nil {
			probs = append(probs, "请选择你自己的游戏 ID")
		} else {
			probs = append(probs, roleProblems(sc, acc, in.Roles)...)
		}
		if len(probs) > 0 {
			return problems(probs)
		}
		tank, damage, support := rolesSet(in.Roles)
		existing, err := GetSignup(txCtx, tx, sc.ID, v.ID)
		if err != nil {
			return err
		}
		if existing == nil {
			if _, err := tx.ExecContext(txCtx, `INSERT INTO scrim_signups
				(scrim_id, user_id, game_account_id, role_tank, role_damage, role_support, created_at, updated_at)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?)`, sc.ID, v.ID, acc.ID, tank, damage, support, db.FormatUTC(now), db.FormatUTC(now)); err != nil {
				return err
			}
		} else {
			changed := existing.GameAccountID == nil || *existing.GameAccountID != acc.ID ||
				b2i(existing.RoleTank) != tank || b2i(existing.RoleDamage) != damage || b2i(existing.RoleSupport) != support
			wasPlaced := existing.Placed()
			if changed {
				// 分队是按旧的游戏 ID 和位置做的，已经过期；替补也算已安排，上场标记在这里清掉，管理员必须知道。
				if _, err := tx.ExecContext(txCtx, `UPDATE scrim_signups SET game_account_id = ?, role_tank = ?, role_damage = ?, role_support = ?,
					is_selected = 0, team = '', assigned_role = '', rating_used = NULL, updated_at = ? WHERE id = ?`,
					acc.ID, tank, damage, support, db.FormatUTC(now), existing.ID); err != nil {
					return err
				}
				if wasPlaced {
					if err := markChanged(txCtx, tx, sc.ID, now); err != nil {
						return err
					}
				}
			}
		}
		out, err = GetSignup(txCtx, tx, sc.ID, v.ID)
		return err
	})
	if isUnique(err) {
		return nil, refuse("你已经报名过这场内战了")
	}
	return out, err
}

func isUnique(err error) bool {
	return err != nil && strings.Contains(err.Error(), "UNIQUE constraint failed")
}

// CancelSignup 取消自己的报名：报名截止后不能取消；已被分队的取消要打标记（规则 158）。
func (s *Service) CancelSignup(ctx *app.Ctx, scrimID int64) error {
	v, err := requireLogin(ctx)
	if err != nil {
		return err
	}
	now := ctx.Now().UTC()
	return s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		sc, err := GetScrim(txCtx, tx, scrimID)
		if err != nil {
			return err
		}
		if sc == nil || !sc.IsPublic() {
			return api.NotFound("内战不存在")
		}
		g, err := GetSignup(txCtx, tx, scrimID, v.ID)
		if err != nil {
			return err
		}
		if g == nil {
			return refuse("你还没有报名这场内战")
		}
		if d := sc.Deadline(); d != nil && now.After(*d) {
			return refuse("报名已截止，不能再取消")
		}
		if _, err := tx.ExecContext(txCtx, `DELETE FROM scrim_signups WHERE id = ?`, g.ID); err != nil {
			return err
		}
		if g.Placed() {
			return markChanged(txCtx, tx, scrimID, now)
		}
		return nil
	})
}
