package tournaments

import (
	"context"
	"strconv"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

// reminderHours 开赛前多少小时提醒，全站设置可配，默认 24（规则 138）。
func reminderHours(ctx context.Context, q db.DBTX) time.Duration {
	h := 24
	var v int
	if err := q.QueryRowContext(ctx, `SELECT tournament_reminder_hours FROM site_settings WHERE id = 1`).Scan(&v); err == nil && v > 0 {
		h = v
	}
	return time.Duration(h) * time.Hour
}

// SendDueReminders 由 worker 每 30 秒跑一次（规则 138–140）：到点（开赛前 24 小时）而赛事一场只发一次。
// 任务执行时重读赛事：时间后移就自我顺延；落在窗口内刚保存的，至少再等 10 分钟才发，免得管理员
// 还在改的时候就发出去了（规则 139）。已通过名单上的每个活跃成员一封；一个都没发出去就不标记已发；
// 散人池的人只有在已有人被编队后才收到提醒（规则 140）。返回发出的信数。
func (s *Service) SendDueReminders(ctx context.Context, now time.Time) (int, error) {
	rd := s.d.ReadPool()
	offset := reminderHours(ctx, rd)
	ts, err := s.loadTournaments(ctx, rd, `WHERE status = 'published' AND starts_at IS NOT NULL AND reminder_sent_at IS NULL`)
	if err != nil {
		return 0, err
	}
	total := 0
	for _, t0 := range ts {
		if !now.Before(*t0.StartsAt) || now.Before(t0.StartsAt.Add(-offset)) || now.Before(t0.UpdatedAt.Add(ReminderGrace)) {
			continue
		}
		sent := 0
		err := s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			t, err := GetTournament(txCtx, tx, t0.ID)
			if err != nil {
				return err
			}
			// 重读：状态、开赛时间、是否已发
			if t == nil || t.Status != StatusPublished || t.StartsAt == nil || t.ReminderSentAt != nil ||
				!now.Before(*t.StartsAt) || now.Before(t.StartsAt.Add(-offset)) || now.Before(t.UpdatedAt.Add(ReminderGrace)) {
				return nil
			}
			rows, err := tx.QueryContext(txCtx, `SELECT u.nickname, u.email, r.team_name, r.team_id IS NULL, m.battletag
				FROM registration_members m JOIN registrations r ON r.id = m.registration_id JOIN users u ON u.id = m.user_id
				WHERE m.tournament_id = ? AND m.is_active = 1 AND r.status = 'approved' AND u.is_active = 1 AND u.email <> ''
				ORDER BY m.id`, t.ID)
			if err != nil {
				return err
			}
			type item struct {
				p      mail.Person
				team   string
				adhoc  bool
				battle string
			}
			var items []item
			for rows.Next() {
				var it item
				var adhoc int
				if err := rows.Scan(&it.p.Name, &it.p.Address, &it.team, &adhoc, &it.battle); err != nil {
					rows.Close()
					return err
				}
				it.adhoc = adhoc == 1
				items = append(items, it)
			}
			rows.Close()
			if err := rows.Err(); err != nil {
				return err
			}
			if len(items) == 0 {
				return nil // 还没有人通过：不标记，之后保存赛事会再安排
			}
			for _, it := range items {
				if err := s.send(txCtx, tx, nil, s.reminderLetter(t, it.team, it.adhoc, it.battle), []mail.Person{it.p}, now); err != nil {
					return err
				}
				sent++
			}
			prow, err := tx.QueryContext(txCtx, `SELECT u.nickname, u.email FROM individual_signups g JOIN users u ON u.id = g.user_id
				WHERE g.tournament_id = ? AND g.registration_id IS NULL AND u.is_active = 1 AND u.email <> '' ORDER BY g.id`, t.ID)
			if err != nil {
				return err
			}
			var pool []mail.Person
			for prow.Next() {
				var p mail.Person
				if err := prow.Scan(&p.Name, &p.Address); err != nil {
					prow.Close()
					return err
				}
				pool = append(pool, p)
			}
			prow.Close()
			for _, p := range pool {
				if err := s.send(txCtx, tx, nil, s.unplacedReminderLetter(t), []mail.Person{p}, now); err != nil {
					return err
				}
				sent++
			}
			_, err = tx.ExecContext(txCtx, `UPDATE tournaments SET reminder_sent_at = ? WHERE id = ? AND reminder_sent_at IS NULL`,
				db.FormatUTC(now), t.ID)
			return err
		})
		if err != nil {
			return total, err
		}
		total += sent
	}
	return total, nil
}

// LiveRegistrations 和 EntriesStillListing 是战队域的 RosterGuard（规则 104、99）。

// LiveRegistrations 战队还有进行中（待审/已通过）、赛事仍是草稿或已发布的报名所在赛事标题，按报名截止排。
func LiveRegistrations(ctx context.Context, q db.DBTX, teamID int64) ([]string, error) {
	rows, err := q.QueryContext(ctx, `SELECT t.title FROM registrations r JOIN tournaments t ON t.id = r.tournament_id
		WHERE r.team_id = ? AND r.status IN ('pending', 'approved') AND t.status IN ('draft', 'published')
		ORDER BY t.registration_closes_at`, teamID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var s string
		if err := rows.Scan(&s); err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

// ListedEntry 对应 teams.ListedEntry；包之间不互相引用，main 里做一层转接。
type ListedEntry struct {
	Title     string
	ClosesAt  *time.Time
	DetailURL string
}

// EntriesStillListing 战队的、赛事仍是草稿或已发布的活跃报名里，还列着这个人的（规则 99）。
func EntriesStillListing(ctx context.Context, q db.DBTX, teamID, userID int64) ([]ListedEntry, error) {
	rows, err := q.QueryContext(ctx, `SELECT DISTINCT r.id, t.title, t.registration_closes_at FROM registrations r
		JOIN tournaments t ON t.id = r.tournament_id JOIN registration_members m ON m.registration_id = r.id
		WHERE r.team_id = ? AND t.status IN ('draft', 'published') AND m.user_id = ? AND m.is_active = 1
		ORDER BY t.registration_closes_at`, teamID, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []ListedEntry
	for rows.Next() {
		var e ListedEntry
		var id int64
		var closes *string
		if err := rows.Scan(&id, &e.Title, &closes); err != nil {
			return nil, err
		}
		if closes != nil {
			if t, err := db.ParseUTC(*closes); err == nil {
				e.ClosesAt = &t
			}
		}
		e.DetailURL = "/registrations/" + strconv.FormatInt(id, 10) + "/"
		out = append(out, e)
	}
	return out, rows.Err()
}
