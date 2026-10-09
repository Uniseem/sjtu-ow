package teams

import (
	"context"
	"fmt"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

// canApply 把设计 7.3 的条件按顺序过一遍，返回能不能申请和该显示的理由（规则 88）。
func (s *Service) canApply(ctx context.Context, q db.DBTX, v *app.Viewer, t *Team) (bool, string, error) {
	if v == nil || v.Disabled || v.ID <= 0 {
		return false, "请先登录。", nil
	}
	if !v.CanUse(accounts.FeatureTeamApply) {
		return false, accounts.FeatureDeniedMessage, nil
	}
	if t.Disbanded() {
		return false, "战队已解散。", nil
	}
	m, err := s.store.GetMembership(ctx, q, t.ID, v.ID)
	if err != nil {
		return false, "", err
	}
	if m != nil {
		return false, "你已经是这支战队的成员了。", nil
	}
	if !t.IsRecruiting {
		return false, "这支战队暂时不招募。", nil
	}
	lim, err := s.store.GetLimits(ctx, q)
	if err != nil {
		return false, "", err
	}
	n, err := s.store.MemberCount(ctx, q, t.ID)
	if err != nil {
		return false, "", err
	}
	if n >= lim.MaxMembers {
		return false, "战队人数已满。", nil
	}
	if stopped, err := s.store.CaptainStopped(ctx, q, t.ID); err != nil {
		return false, "", err
	} else if stopped {
		return false, CaptainStopped, nil
	}
	if g, err := s.store.GameAccountCount(ctx, q, v.ID); err != nil {
		return false, "", err
	} else if g == 0 {
		return false, "请先在个人中心添加至少一个游戏 ID。", nil
	}
	if pending, err := s.store.HasPendingApplication(ctx, q, t.ID, v.ID); err != nil {
		return false, "", err
	} else if pending {
		return false, "你对这支战队还有一条待审批的申请。", nil
	}
	return true, "", nil
}

// ApplyInput 是入队申请的入参。
type ApplyInput struct {
	TeamID  int64    `json:"-"`
	Roles   []string `json:"roles"`
	Message string   `json:"message"`
}

// Apply 提交入队申请（规则 88–91）。
func (s *Service) Apply(ctx *app.Ctx, in ApplyInput) (*Application, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	t, err := s.store.GetTeam(ctx.Context, s.d.ReadPool(), in.TeamID)
	if err != nil {
		return nil, err
	}
	if t == nil {
		return nil, api.NotFound("战队不存在")
	}
	roles := accounts.ParseRoles(strings.Join(in.Roles, ","))
	message := strings.TrimSpace(in.Message)
	fields := map[string][]string{}
	if len(roles) == 0 {
		fields["roles"] = []string{"请至少选择一个意向位置。"}
	}
	if utf8.RuneCountInString(message) > MessageMax {
		fields["message"] = []string{fmt.Sprintf("留言最多 %d 字。", MessageMax)}
	}
	if len(fields) > 0 {
		return nil, api.InvalidFields(fields)
	}
	ok, reason, err := s.canApply(ctx.Context, s.d.ReadPool(), v, t)
	if err != nil {
		return nil, err
	}
	if !ok {
		return nil, refuse(reason)
	}
	if s.limiter != nil {
		retry, allowed, err := s.limiter.Allow(ctx.Context, fmt.Sprintf("u:%d", v.ID), ratelimit.TeamApply)
		if err != nil {
			return nil, err
		}
		if !allowed {
			return nil, api.TooManyRequests(retry)
		}
	}

	now := ctx.Now().UTC()
	has := func(code string) int {
		for _, r := range roles {
			if r == code {
				return 1
			}
		}
		return 0
	}
	var created *Application
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		// 事务里重查一遍：双击发出的两个请求，第二个要被「还有一条待审批」拦下（216 T5）。
		t2, err := s.store.GetTeam(txCtx, tx, in.TeamID)
		if err != nil {
			return err
		}
		if ok, reason, err := s.canApply(txCtx, tx, v, t2); err != nil {
			return err
		} else if !ok {
			return refuse(reason)
		}
		res, err := tx.ExecContext(txCtx, `INSERT INTO team_applications
			(team_id, applicant_id, role_tank, role_damage, role_support, message, status, created_at)
			VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)`,
			in.TeamID, v.ID, has("tank"), has("damage"), has("support"), message, db.FormatUTC(now))
		if err != nil {
			return err
		}
		id, err := res.LastInsertId()
		if err != nil {
			return err
		}
		created, err = s.store.GetApplication(txCtx, tx, id)
		if err != nil {
			return err
		}
		return s.notifySubmitted(txCtx, tx, ctx, t2, created, now)
	})
	if isUnique(err) {
		return nil, refuse("你对这支战队还有一条待审批的申请。")
	}
	if err != nil {
		return nil, err
	}
	if message != "" && s.mod != nil {
		if err := s.mod.Submit(ctx.Context, "application_message", created.ID, "message", message,
			fmt.Sprintf("/teams/%d/manage/", t.ID), v.ID); err != nil {
			logWarn("送审失败", "application_message", created.ID, err)
		}
	}
	return created, nil
}

// Approve 通过一条申请（规则 92、93）。在一个写事务里重新检查：申请人注销或停用，申请
// 自动取消并报错；已经是成员，同样取消并报错；满员拒绝通过。
func (s *Service) Approve(ctx *app.Ctx, applicationID int64) (*Application, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	var out *Application
	var after error
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		a, err := s.store.GetApplication(txCtx, tx, applicationID)
		if err != nil {
			return err
		}
		if a == nil {
			return api.NotFound("申请不存在")
		}
		t, err := s.store.GetTeam(txCtx, tx, a.TeamID)
		if err != nil {
			return err
		}
		if ok, err := s.isManager(txCtx, tx, v, a.TeamID); err != nil {
			return err
		} else if !ok {
			return deny("只有队长可以审批入队申请。")
		}
		if a.Status != StatusPending {
			return refuse("这条申请已经处理过了。")
		}
		if t.Disbanded() {
			return refuse("战队已解散。")
		}
		applicant, err := s.user(txCtx, tx, a.ApplicantID)
		if err != nil {
			return err
		}
		existing, err := s.store.GetMembership(txCtx, tx, a.TeamID, a.ApplicantID)
		if err != nil {
			return err
		}
		switch {
		case applicant == nil || !applicant.Active:
			// 注销或停用的人进不了队；在这里把申请关掉，事务提交后再报错。
			if err := s.store.DecideApplication(txCtx, tx, a.ID, StatusCancelled, &v.ID, now, GoneNote); err != nil {
				return err
			}
			after = refuse("申请人的账号已注销或停用，这条申请已关闭。")
		case existing != nil:
			// 在事务里 raise 会把关闭一起回滚，申请就永远待审（059）。
			if err := s.store.DecideApplication(txCtx, tx, a.ID, StatusCancelled, &v.ID, now, "申请人已经是成员"); err != nil {
				return err
			}
			after = refuse("申请人已经是这支战队的成员了。")
		default:
			lim, err := s.store.GetLimits(txCtx, tx)
			if err != nil {
				return err
			}
			n, err := s.store.MemberCount(txCtx, tx, a.TeamID)
			if err != nil {
				return err
			}
			if n >= lim.MaxMembers {
				return refuse("战队人数已满，无法通过。")
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO team_memberships (team_id, user_id, role, joined_at)
				VALUES (?, ?, 'member', ?)`, a.TeamID, a.ApplicantID, db.FormatUTC(now)); err != nil {
				return err
			}
			if err := s.store.UnretireTx(txCtx, tx, a.TeamID, a.ApplicantID); err != nil {
				return err
			}
			if err := s.store.DecideApplication(txCtx, tx, a.ID, StatusApproved, &v.ID, now, ""); err != nil {
				return err
			}
			if err := s.store.Touch(txCtx, tx, a.TeamID, now); err != nil {
				return err
			}
			a.Status = StatusApproved
			if err := s.notifyDecided(txCtx, tx, ctx, t, a, applicant, now); err != nil {
				return err
			}
		}
		out, err = s.store.GetApplication(txCtx, tx, applicationID)
		return err
	})
	if err != nil {
		return nil, err
	}
	if after != nil {
		return nil, after
	}
	return out, nil
}

// RejectInput 是拒绝申请的入参。
type RejectInput struct {
	ID   int64  `json:"-"`
	Note string `json:"note"`
}

// Reject 拒绝一条申请，原因可以不填，最多 200 字。
func (s *Service) Reject(ctx *app.Ctx, in RejectInput) (*Application, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	note := strings.TrimSpace(in.Note)
	if utf8.RuneCountInString(note) > MessageMax {
		return nil, api.InvalidFields(map[string][]string{"note": {fmt.Sprintf("原因最多 %d 字。", MessageMax)}})
	}
	now := ctx.Now().UTC()
	var out *Application
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		a, err := s.store.GetApplication(txCtx, tx, in.ID)
		if err != nil {
			return err
		}
		if a == nil {
			return api.NotFound("申请不存在")
		}
		if ok, err := s.isManager(txCtx, tx, v, a.TeamID); err != nil {
			return err
		} else if !ok {
			return deny("只有队长可以审批入队申请。")
		}
		if a.Status != StatusPending {
			return refuse("这条申请已经处理过了。")
		}
		if err := s.store.DecideApplication(txCtx, tx, a.ID, StatusRejected, &v.ID, now, note); err != nil {
			return err
		}
		t, err := s.store.GetTeam(txCtx, tx, a.TeamID)
		if err != nil {
			return err
		}
		applicant, err := s.user(txCtx, tx, a.ApplicantID)
		if err != nil {
			return err
		}
		out, err = s.store.GetApplication(txCtx, tx, a.ID)
		if err != nil {
			return err
		}
		return s.notifyDecided(txCtx, tx, ctx, t, out, applicant, now)
	})
	return out, err
}

// Cancel 申请人撤回自己的待审申请。
func (s *Service) Cancel(ctx *app.Ctx, applicationID int64) (*Application, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	var out *Application
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		a, err := s.store.GetApplication(txCtx, tx, applicationID)
		if err != nil {
			return err
		}
		if a == nil {
			return api.NotFound("申请不存在")
		}
		if a.ApplicantID != v.ID {
			return deny("只能撤回自己的申请。")
		}
		if a.Status != StatusPending {
			return refuse("这条申请已经处理过了。")
		}
		if err := s.store.DecideApplication(txCtx, tx, a.ID, StatusCancelled, nil, now, ""); err != nil {
			return err
		}
		out, err = s.store.GetApplication(txCtx, tx, a.ID)
		return err
	})
	return out, err
}

// RemindCaptains 待审满 7 天的申请，每队给队长发一封汇总提醒（规则 94）。
// captain_reminded_at 保证每条申请只被提到一次。返回发出的信数。
func (s *Service) RemindCaptains(ctx context.Context, now time.Time) (int, error) {
	cutoff := db.FormatUTC(now.Add(-RemindCaptainDays * 24 * time.Hour))
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT a.id, a.team_id FROM team_applications a
		JOIN teams t ON t.id = a.team_id
		JOIN users u ON u.id = a.applicant_id
		WHERE a.status = 'pending' AND a.created_at < ? AND a.captain_reminded_at IS NULL
			AND t.disbanded_at IS NULL AND u.is_active = 1
		ORDER BY a.team_id, a.created_at`, cutoff)
	if err != nil {
		return 0, err
	}
	byTeam := map[int64][]int64{}
	var order []int64
	for rows.Next() {
		var id, teamID int64
		if err := rows.Scan(&id, &teamID); err != nil {
			rows.Close()
			return 0, err
		}
		if _, seen := byTeam[teamID]; !seen {
			order = append(order, teamID)
		}
		byTeam[teamID] = append(byTeam[teamID], id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}

	sent := 0
	for _, teamID := range order {
		ids := byTeam[teamID]
		err := s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			t, err := s.store.GetTeam(txCtx, tx, teamID)
			if err != nil {
				return err
			}
			var apps []*Application
			for _, id := range ids {
				a, err := s.store.GetApplication(txCtx, tx, id)
				if err != nil {
					return err
				}
				if a != nil {
					apps = append(apps, a)
				}
			}
			captain, err := s.store.CaptainOf(txCtx, tx, teamID)
			if err != nil {
				return err
			}
			if captain != nil {
				if u, err := s.user(txCtx, tx, captain.UserID); err != nil {
					return err
				} else if u != nil && u.Active && u.Email != "" {
					if err := s.notifyWaiting(txCtx, tx, t, apps, u, now); err != nil {
						return err
					}
					sent++
				}
			}
			for _, id := range ids {
				if _, err := tx.ExecContext(txCtx, `UPDATE team_applications SET captain_reminded_at = ? WHERE id = ?`,
					db.FormatUTC(now), id); err != nil {
					return err
				}
			}
			return nil
		})
		if err != nil {
			return sent, err
		}
	}
	return sent, nil
}

// CloseStaleApplications 待审满 14 天无人处理的申请自动关闭，并通知申请人（规则 95）。
func (s *Service) CloseStaleApplications(ctx context.Context, now time.Time) (int, error) {
	cutoff := db.FormatUTC(now.Add(-StaleApplicationDays * 24 * time.Hour))
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT id FROM team_applications
		WHERE status = 'pending' AND created_at < ? ORDER BY id`, cutoff)
	if err != nil {
		return 0, err
	}
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return 0, err
		}
		ids = append(ids, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}
	closed := 0
	note := fmt.Sprintf("队长 %d 天没有处理，申请自动关闭", StaleApplicationDays)
	for _, id := range ids {
		err := s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			a, err := s.store.GetApplication(txCtx, tx, id)
			if err != nil || a == nil || a.Status != StatusPending {
				return err
			}
			if err := s.store.DecideApplication(txCtx, tx, id, StatusCancelled, nil, now, note); err != nil {
				return err
			}
			closed++
			applicant, err := s.user(txCtx, tx, a.ApplicantID)
			if err != nil {
				return err
			}
			if applicant != nil && applicant.Active {
				t, err := s.store.GetTeam(txCtx, tx, a.TeamID)
				if err != nil {
					return err
				}
				return s.notifyExpired(txCtx, tx, t, applicant, now)
			}
			return nil
		})
		if err != nil {
			return closed, err
		}
	}
	return closed, nil
}
