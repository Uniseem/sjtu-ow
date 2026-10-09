package teams

import (
	"context"
	"log/slog"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func logWarn(msg, target string, id int64, err error) {
	slog.Warn(msg, "target", target, "id", id, "err", err.Error())
}

// Leave 队员退出战队（规则 97、98、99）。队长不能直接退，要先转让或解散。
func (s *Service) Leave(ctx *app.Ctx, teamID int64) error {
	v, err := requireLogin(ctx)
	if err != nil {
		return err
	}
	now := ctx.Now().UTC()
	return s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		t, err := s.store.GetTeam(txCtx, tx, teamID)
		if err != nil {
			return err
		}
		if t == nil {
			return api.NotFound("战队不存在")
		}
		m, err := s.store.GetMembership(txCtx, tx, teamID, v.ID)
		if err != nil {
			return err
		}
		if m == nil {
			return refuse("你不是这支战队的成员。")
		}
		if m.Role == RoleCaptain {
			return refuse("队长不能直接退出，请先转让队长或解散战队。")
		}
		if err := s.store.RetireTx(txCtx, tx, m, LeaveLeft, now); err != nil {
			return err
		}
		if _, err := tx.ExecContext(txCtx, `DELETE FROM team_memberships WHERE id = ?`, m.ID); err != nil {
			return err
		}
		if err := s.store.Touch(txCtx, tx, teamID, now); err != nil {
			return err
		}
		return s.notifyLeft(txCtx, tx, ctx, t, v.ID, now)
	})
}

// RemoveMember 队长（或超管）移除一名队员（规则 100）。不能移除自己，也不能移除队长。
func (s *Service) RemoveMember(ctx *app.Ctx, teamID, userID int64) error {
	v, err := requireLogin(ctx)
	if err != nil {
		return err
	}
	now := ctx.Now().UTC()
	return s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		t, err := s.store.GetTeam(txCtx, tx, teamID)
		if err != nil {
			return err
		}
		if t == nil {
			return api.NotFound("战队不存在")
		}
		if ok, err := s.isManager(txCtx, tx, v, teamID); err != nil {
			return err
		} else if !ok {
			return deny("只有队长可以移除成员。")
		}
		if userID == v.ID {
			return refuse("不能移除自己。")
		}
		m, err := s.store.GetMembership(txCtx, tx, teamID, userID)
		if err != nil {
			return err
		}
		if m == nil {
			return refuse("这个人不是战队成员。")
		}
		if m.Role == RoleCaptain {
			// 超管也不行：移除了队长，战队就没有队长了。先转让（216）。
			return refuse("不能移除队长，先把队长转给别人。")
		}
		if err := s.store.RetireTx(txCtx, tx, m, LeaveRemoved, now); err != nil {
			return err
		}
		if _, err := tx.ExecContext(txCtx, `DELETE FROM team_memberships WHERE id = ?`, m.ID); err != nil {
			return err
		}
		if err := s.store.Touch(txCtx, tx, teamID, now); err != nil {
			return err
		}
		return s.notifyRemoved(txCtx, tx, ctx, t, userID, now)
	})
}

// handOver 在事务里把队长交给 target（已经是成员）。规则 102 的检查都在这里。
func (s *Service) handOver(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Team, targetID int64, now time.Time) error {
	target, err := s.store.GetMembership(ctx, tx, t.ID, targetID)
	if err != nil {
		return err
	}
	if target == nil {
		return refuse("只能转让给现有成员。")
	}
	u, err := s.user(ctx, tx, targetID)
	if err != nil {
		return err
	}
	if u == nil || !u.Active {
		// 停用的人当队长，没人能审批申请，要超管出面（213 T2）。
		return refuse("这个账号已停用，不能当队长。")
	}
	if target.Role == RoleCaptain {
		return refuse("这位成员已经是队长了。")
	}
	lim, err := s.store.GetLimits(ctx, tx)
	if err != nil {
		return err
	}
	n, err := s.store.CaptainedCount(ctx, tx, targetID)
	if err != nil {
		return err
	}
	if n >= lim.MaxCaptained {
		return refuse("对方担任队长的战队已达上限。")
	}
	// 每队至多一个队长：先降旧的，再升新的。
	if _, err := tx.ExecContext(ctx, `UPDATE team_memberships SET role = 'member'
		WHERE team_id = ? AND role = 'captain'`, t.ID); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `UPDATE team_memberships SET role = 'captain' WHERE id = ?`, target.ID); err != nil {
		return err
	}
	if err := s.store.Touch(ctx, tx, t.ID, now); err != nil {
		return err
	}
	return s.notifyCaptainChanged(ctx, tx, c, t, u, now)
}

// TransferCaptain 把队长转给现有成员（规则 102）。
func (s *Service) TransferCaptain(ctx *app.Ctx, teamID, userID int64) error {
	v, err := requireLogin(ctx)
	if err != nil {
		return err
	}
	now := ctx.Now().UTC()
	return s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		t, err := s.store.GetTeam(txCtx, tx, teamID)
		if err != nil {
			return err
		}
		if t == nil {
			return api.NotFound("战队不存在")
		}
		if ok, err := s.isManager(txCtx, tx, v, teamID); err != nil {
			return err
		} else if !ok {
			return deny("只有队长可以转让队长。")
		}
		return s.handOver(txCtx, tx, ctx, t, userID, now)
	})
}

// AssignCaptain 超管指定队长（规则 103）：队长账号没了的救援路径。目标不在队里时先入队，
// 满员就拒绝；整个流程一个事务，转让被拒时不会留下一个刚入队的人。
func (s *Service) AssignCaptain(ctx *app.Ctx, teamID, userID int64) error {
	v, err := requireLogin(ctx)
	if err != nil {
		return err
	}
	if !v.Superuser {
		return deny("只有超级管理员可以指定队长。")
	}
	now := ctx.Now().UTC()
	return s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		t, err := s.store.GetTeam(txCtx, tx, teamID)
		if err != nil {
			return err
		}
		if t == nil {
			return api.NotFound("战队不存在")
		}
		if t.Disbanded() {
			return refuse("战队已经解散了，不能再指定队长。")
		}
		u, err := s.user(txCtx, tx, userID)
		if err != nil {
			return err
		}
		if u == nil {
			return api.NotFound("用户不存在")
		}
		if !u.Active {
			return refuse("这个账号已停用，不能当队长。")
		}
		m, err := s.store.GetMembership(txCtx, tx, teamID, userID)
		if err != nil {
			return err
		}
		if m == nil {
			lim, err := s.store.GetLimits(txCtx, tx)
			if err != nil {
				return err
			}
			n, err := s.store.MemberCount(txCtx, tx, teamID)
			if err != nil {
				return err
			}
			if n >= lim.MaxMembers {
				return refuse("战队人数已满，先移除一名成员，或者从现有成员里指定。")
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO team_memberships (team_id, user_id, role, joined_at)
				VALUES (?, ?, 'member', ?)`, teamID, userID, db.FormatUTC(now)); err != nil {
				return err
			}
			if err := s.store.UnretireTx(txCtx, tx, teamID, userID); err != nil {
				return err
			}
		}
		return s.handOver(txCtx, tx, ctx, t, userID, now)
	})
}

// DisbandBlockers 说明战队为什么现在不能解散：还有进行中的报名（规则 104）。
func (s *Service) disbandBlockers(ctx context.Context, q db.DBTX, teamID int64) ([]string, error) {
	if s.rosters == nil {
		return nil, nil
	}
	titles, err := s.rosters.LiveRegistrations(ctx, q, teamID)
	if err != nil {
		return nil, err
	}
	out := make([]string, 0, len(titles))
	for _, title := range titles {
		out = append(out, "战队还在赛事「"+title+"」的报名里，请先撤回报名。")
	}
	return out, nil
}

// Disband 解散战队（规则 104、105）：置解散时间，删全部成员关系，待审申请全部取消，
// 通知全体成员。解散是软删除，报名还指着它；解散不写退役记录。
func (s *Service) Disband(ctx *app.Ctx, teamID int64) error {
	v, err := requireLogin(ctx)
	if err != nil {
		return err
	}
	now := ctx.Now().UTC()
	return s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		t, err := s.store.GetTeam(txCtx, tx, teamID)
		if err != nil {
			return err
		}
		if t == nil {
			return api.NotFound("战队不存在")
		}
		if ok, err := s.isManager(txCtx, tx, v, teamID); err != nil {
			return err
		} else if !ok {
			return deny("只有队长或超级管理员可以解散战队。")
		}
		if t.Disbanded() {
			return refuse("战队已经解散了。")
		}
		blockers, err := s.disbandBlockers(txCtx, tx, teamID)
		if err != nil {
			return err
		}
		if len(blockers) > 0 {
			return refuse(strings.Join(blockers, "；"))
		}
		members, err := s.memberIDs(txCtx, tx, teamID)
		if err != nil {
			return err
		}
		if _, err := tx.ExecContext(txCtx, `UPDATE teams SET disbanded_at = ?, version = version + 1, updated_at = ?
			WHERE id = ?`, db.FormatUTC(now), db.FormatUTC(now), teamID); err != nil {
			return err
		}
		if _, err := tx.ExecContext(txCtx, `DELETE FROM team_memberships WHERE team_id = ?`, teamID); err != nil {
			return err
		}
		if _, err := tx.ExecContext(txCtx, `UPDATE team_applications
			SET status = 'cancelled', decided_at = ?, decision_note = '战队已解散'
			WHERE team_id = ? AND status = 'pending'`, db.FormatUTC(now), teamID); err != nil {
			return err
		}
		return s.notifyDisbanded(txCtx, tx, ctx, t, members, now)
	})
}

func (s *Service) memberIDs(ctx context.Context, q db.DBTX, teamID int64) ([]int64, error) {
	rows, err := q.QueryContext(ctx, `SELECT user_id FROM team_memberships WHERE team_id = ? ORDER BY id`, teamID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	return ids, rows.Err()
}

// RemoveAlumnus 本人、队长或超管把一条退役记录从战队页上去掉（规则 101）。
func (s *Service) RemoveAlumnus(ctx *app.Ctx, alumnusID int64) error {
	v, err := requireLogin(ctx)
	if err != nil {
		return err
	}
	now := ctx.Now().UTC()
	return s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		var teamID, userID int64
		err := tx.QueryRowContext(txCtx, `SELECT team_id, user_id FROM team_alumni WHERE id = ?`, alumnusID).
			Scan(&teamID, &userID)
		if err != nil {
			return api.NotFound("记录不存在")
		}
		allowed := v.Superuser || v.ID == userID
		if !allowed {
			allowed, err = s.isManager(txCtx, tx, v, teamID)
			if err != nil {
				return err
			}
		}
		if !allowed {
			return deny("只有本人或队长可以去掉这条记录。")
		}
		if _, err := tx.ExecContext(txCtx, `DELETE FROM team_alumni WHERE id = ?`, alumnusID); err != nil {
			return err
		}
		return s.store.Touch(txCtx, tx, teamID, now)
	})
}
