package scrims

import (
	"context"
	"database/sql"
	"fmt"
	"log/slog"
	"math/rand"
	"net/http"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/markdown"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
)

// ViewerBuilder 按用户编号组出他的 Viewer（can_use 的判定要它）。
type ViewerBuilder func(ctx context.Context, userID int64) (*app.Viewer, error)

// Service 协调内战域的业务规则（设计 9）。
type Service struct {
	d       *db.DB
	siteURL string
	viewers ViewerBuilder
	rng     *rand.Rand
}

// NewService 造内战服务；d 可以是 nil（apigen）。
func NewService(d *db.DB, siteURL string) *Service {
	return &Service{d: d, siteURL: strings.TrimRight(siteURL, "/")}
}

// SetRand 换随机源（测试里要可复现的分队）。
func (s *Service) SetRand(r *rand.Rand) { s.rng = r }

// SetViewerBuilder 接上 Viewer 的组装。
func (s *Service) SetViewerBuilder(b ViewerBuilder) { s.viewers = b }

func refuse(msg string) *api.Error { return api.NewErr(http.StatusConflict, "refused", msg) }

func problems(list []string) error {
	return api.InvalidFields(map[string][]string{"__all__": list})
}

func requireLogin(ctx *app.Ctx) (*app.Viewer, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	return ctx.Viewer, nil
}

func requireManager(ctx *app.Ctx) (*app.Viewer, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	if !v.HasCap(accounts.CapScrimsManage) {
		return nil, api.Forbidden()
	}
	return v, nil
}

var shanghai = time.FixedZone("Asia/Shanghai", 8*3600)

func moment(t time.Time) string { return t.In(shanghai).Format("2006-01-02 15:04") }

func (s *Service) scrimURL(id int64) string { return fmt.Sprintf("%s/scrims/%d/", s.siteURL, id) }

func (s *Service) send(ctx context.Context, tx *db.Tx, c *app.Ctx, l mail.Letter, to []mail.Person, now time.Time) error {
	var batch *app.LetterBatch
	if c != nil {
		batch = c.Letters
	}
	_, err := outbox.Send(ctx, tx, batch, s.siteURL, l, to, now)
	return err
}

// Missing 草稿离发布还缺什么（规则 145）。
func Missing(sc *Scrim) []string {
	var gaps []string
	if strings.TrimSpace(sc.Title) == "" {
		gaps = append(gaps, "标题")
	}
	if sc.StartsAt == nil {
		gaps = append(gaps, "开始时间")
	}
	return gaps
}

// CreateScrim 建一个空白草稿。
func (s *Service) CreateScrim(ctx *app.Ctx) (*Scrim, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	now := db.FormatUTC(ctx.Now().UTC())
	var out *Scrim
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `INSERT INTO scrims (created_by, created_at, updated_at) VALUES (?, ?, ?)`, v.ID, now, now)
		if err != nil {
			return err
		}
		id, err := res.LastInsertId()
		if err != nil {
			return err
		}
		out, err = GetScrim(txCtx, tx, id)
		return err
	})
	return out, err
}

// Changes 是这次要改的字段，没出现的不动。时间用 RFC3339 文本，空串表示清空。
type Changes struct {
	Title          *string `json:"title,omitempty"`
	Description    *string `json:"description,omitempty"`
	StartsAt       *string `json:"starts_at,omitempty"`
	SignupClosesAt *string `json:"signup_closes_at,omitempty"`
	Format         *string `json:"format,omitempty"`
	SjtuOnly       *bool   `json:"sjtu_only,omitempty"`
}

// SaveResult 是自动保存的回答（12 号文档 5.5）。
type SaveResult struct {
	Version int64               `json:"version"`
	Saved   []string            `json:"saved"`
	Fields  map[string][]string `json:"fields,omitempty"`
	SavedAt time.Time           `json:"saved_at"`
}

func parseWhen(raw string) (*time.Time, bool) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil, true
	}
	t, err := time.Parse(time.RFC3339, raw)
	if err != nil {
		return nil, false
	}
	u := t.UTC()
	return &u, true
}

func sameTime(a, b *time.Time) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return a.Equal(*b)
}

// UpdateScrim 按字段保存：合法的存，不合法的留旧值。改期按规则 152。
func (s *Service) UpdateScrim(ctx *app.Ctx, id, baseVersion int64, ch Changes) (*SaveResult, error) {
	if _, err := requireManager(ctx); err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	res := &SaveResult{Fields: map[string][]string{}, SavedAt: now}
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		sc, err := GetScrim(txCtx, tx, id)
		if err != nil {
			return err
		}
		if sc == nil {
			return api.NotFound("内战不存在")
		}
		if baseVersion != sc.Version {
			return api.NewErr(http.StatusConflict, "stale", "另一个人刚改过，已换成最新内容")
		}
		var sets []string
		var args []any
		set := func(field, col string, val any) {
			sets = append(sets, col+" = ?")
			args = append(args, val)
			res.Saved = append(res.Saved, field)
		}
		bad := func(field, msg string) { res.Fields[field] = append(res.Fields[field], msg) }
		if ch.Title != nil {
			x := strings.TrimSpace(*ch.Title)
			if utf8.RuneCountInString(x) > 100 {
				bad("title", "标题最多 100 字。")
			} else if x != sc.Title {
				set("title", "title", x)
			}
		}
		if ch.Description != nil && *ch.Description != sc.Description {
			_, plain, _, _, _, _ := markdown.Facts(*ch.Description, s.siteURL, nil)
			set("description", "description", *ch.Description)
			sets = append(sets, "description_plain = ?")
			args = append(args, plain)
		}
		if ch.SjtuOnly != nil && *ch.SjtuOnly != sc.SjtuOnly {
			set("sjtu_only", "sjtu_only", b2i(*ch.SjtuOnly))
		}
		if ch.Format != nil && *ch.Format != sc.Format {
			if _, ok := FormatLabels[*ch.Format]; !ok {
				bad("format", "规格不对。")
			} else {
				set("format", "format", *ch.Format)
			}
		}
		newStarts, startsChanged := sc.StartsAt, false
		if ch.StartsAt != nil {
			p, ok := parseWhen(*ch.StartsAt)
			if !ok {
				bad("starts_at", "时间格式不对。")
			} else if !sameTime(p, sc.StartsAt) {
				set("starts_at", "starts_at", timeArg(p))
				newStarts, startsChanged = p, true
			}
		}
		if ch.SignupClosesAt != nil {
			p, ok := parseWhen(*ch.SignupClosesAt)
			if !ok {
				bad("signup_closes_at", "时间格式不对。")
			} else if !sameTime(p, sc.SignupClosesAt) {
				set("signup_closes_at", "signup_closes_at", timeArg(p))
			}
		}
		// 改期（规则 152）：已发布、新时间在未来且变了才触发，同赛事规则
		if startsChanged && sc.Status == StatusPublished && sc.StartsAt != nil && newStarts != nil && newStarts.After(now) {
			told := sc.MovedFrom
			if told == nil {
				told = sc.StartsAt
			}
			var movedFrom any
			if !told.Equal(*newStarts) {
				movedFrom = db.FormatUTC(*told)
			}
			sets = append(sets, "reminder_sent_at = NULL", "moved_from = ?")
			args = append(args, movedFrom)
		}
		res.Version = sc.Version
		if len(sets) > 0 {
			sets = append(sets, "version = version + 1", "updated_at = ?")
			args = append(args, db.FormatUTC(now), id)
			if _, err := tx.ExecContext(txCtx, `UPDATE scrims SET `+strings.Join(sets, ", ")+` WHERE id = ?`, args...); err != nil {
				return err
			}
			res.Version = sc.Version + 1
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	if len(res.Fields) == 0 {
		res.Fields = nil
	}
	return res, nil
}

func (s *Service) transition(ctx *app.Ctx, id int64, fn func(sc *Scrim, tx *db.Tx, txCtx context.Context, now time.Time) (string, error)) (*Scrim, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	var out *Scrim
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		sc, err := GetScrim(txCtx, tx, id)
		if err != nil {
			return err
		}
		if sc == nil {
			return api.NotFound("内战不存在")
		}
		status, err := fn(sc, tx, txCtx, now)
		if err != nil {
			return err
		}
		if status != "" {
			if _, err := tx.ExecContext(txCtx, `UPDATE scrims SET status = ?, version = version + 1, updated_at = ?,
				created_by = COALESCE(created_by, ?) WHERE id = ?`, status, db.FormatUTC(now), v.ID, id); err != nil {
				return err
			}
		}
		out, err = GetScrim(txCtx, tx, id)
		return err
	})
	return out, err
}

// Publish 发布（规则 144、145）：只有草稿能发布，已取消/已结束/已发布的各有说法；缺东西不能发。
func (s *Service) Publish(ctx *app.Ctx, id int64) (*Scrim, error) {
	return s.transition(ctx, id, func(sc *Scrim, _ *db.Tx, _ context.Context, _ time.Time) (string, error) {
		switch sc.Status {
		case StatusCancelled:
			return "", refuse("已取消的内战不能再发布。")
		case StatusFinished:
			return "", refuse("已结束的内战不能再发布。")
		case StatusPublished:
			return "", refuse("这场内战已经发布了。")
		}
		if gaps := Missing(sc); len(gaps) > 0 {
			return "", refuse("还没填好：" + strings.Join(gaps, "、") + "。填好再发布。")
		}
		return StatusPublished, nil
	})
}

// Finish 标记已结束：只有已发布的（规则 144）。
func (s *Service) Finish(ctx *app.Ctx, id int64) (*Scrim, error) {
	return s.transition(ctx, id, func(sc *Scrim, _ *db.Tx, _ context.Context, _ time.Time) (string, error) {
		if sc.Status != StatusPublished {
			return "", refuse("只有已发布的内战可以标记为已结束。")
		}
		return StatusFinished, nil
	})
}

// Cancel 取消（规则 146、150）：没填好的草稿直接删除；取消通知所有活跃且有邮箱的报名者。
func (s *Service) Cancel(ctx *app.Ctx, id int64) (*Scrim, error) {
	return s.transition(ctx, id, func(sc *Scrim, tx *db.Tx, txCtx context.Context, now time.Time) (string, error) {
		if sc.Status == StatusCancelled {
			return "", refuse("这场内战已经取消了。")
		}
		if sc.Status == StatusDraft && len(Missing(sc)) > 0 {
			return "", refuse("还没填好的草稿不用取消，直接删除。")
		}
		people, err := s.participants(txCtx, tx, id)
		if err != nil {
			return "", err
		}
		when := "时间未定"
		if sc.StartsAt != nil {
			when = moment(*sc.StartsAt)
		}
		err = s.send(txCtx, tx, ctx, mail.Letter{
			Subject:    "内战已取消：" + sc.Title,
			Lead:       fmt.Sprintf("内战「%s」取消了，原定的时间不用再留出来。", sc.Title),
			Facts:      [][2]string{{"开始时间", when}, {"规格", FormatLabels[sc.Format]}},
			Paragraphs: []string{"之后有新的内战会在网站上公布。"},
			Action:     []string{"查看活动页面", s.scrimURL(id)},
			Reason:     fmt.Sprintf("你收到这封邮件，是因为你报名了内战「%s」。", sc.Title),
		}, people, now)
		return StatusCancelled, err
	})
}

// DeleteScrim 只有没人报名的草稿能删（规则 146）。
func (s *Service) DeleteScrim(ctx *app.Ctx, id int64) error {
	if _, err := requireManager(ctx); err != nil {
		return err
	}
	return s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		sc, err := GetScrim(txCtx, tx, id)
		if err != nil {
			return err
		}
		if sc == nil {
			return api.NotFound("内战不存在")
		}
		if sc.Status != StatusDraft {
			return refuse("发布过的内战只能取消，不能删除。")
		}
		var n int
		if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM scrim_signups WHERE scrim_id = ?`, id).Scan(&n); err != nil {
			return err
		}
		if n > 0 {
			return refuse("已经有人报名，不能删除。")
		}
		_, err = tx.ExecContext(txCtx, `DELETE FROM scrims WHERE id = ?`, id)
		return err
	})
}

const week = 7 * 24 * time.Hour

func weeksAhead(times []*time.Time, now time.Time) time.Duration {
	var earliest *time.Time
	for _, t := range times {
		if t != nil && (earliest == nil || t.Before(*earliest)) {
			earliest = t
		}
	}
	if earliest == nil || earliest.Add(week).After(now) {
		return week
	}
	return (now.Sub(*earliest)/week + 1) * week
}

// Copy 复制为新草稿（规则 169）：只抄标题、说明、规格、仅限交大，两个时间整周平移。
func (s *Service) Copy(ctx *app.Ctx, id int64) (*Scrim, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	var out *Scrim
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		sc, err := GetScrim(txCtx, tx, id)
		if err != nil {
			return err
		}
		if sc == nil {
			return api.NotFound("内战不存在")
		}
		shift := weeksAhead([]*time.Time{sc.StartsAt, sc.SignupClosesAt}, now)
		move := func(p *time.Time) any {
			if p == nil {
				return nil
			}
			return db.FormatUTC(p.Add(shift))
		}
		var plain string
		_, plain, _, _, _, _ = markdown.Facts(sc.Description, s.siteURL, nil)
		res, err := tx.ExecContext(txCtx, `INSERT INTO scrims (title, description, description_plain, starts_at, signup_closes_at,
			format, sjtu_only, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
			sc.Title, sc.Description, plain, move(sc.StartsAt), move(sc.SignupClosesAt), sc.Format, b2i(sc.SjtuOnly), v.ID,
			db.FormatUTC(now), db.FormatUTC(now))
		if err != nil {
			return err
		}
		nid, err := res.LastInsertId()
		if err != nil {
			return err
		}
		out, err = GetScrim(txCtx, tx, nid)
		return err
	})
	return out, err
}

// NotifyParticipants 「通知报名的人」（规则 152）。
func (s *Service) NotifyParticipants(ctx *app.Ctx, id int64, note string) (int, error) {
	if _, err := requireManager(ctx); err != nil {
		return 0, err
	}
	note = strings.TrimSpace(note)
	if utf8.RuneCountInString(note) > NotifyNoteMax {
		return 0, api.InvalidFields(map[string][]string{"note": {fmt.Sprintf("说明最多 %d 字。", NotifyNoteMax)}})
	}
	now := ctx.Now().UTC()
	count := 0
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		sc, err := GetScrim(txCtx, tx, id)
		if err != nil {
			return err
		}
		if sc == nil {
			return api.NotFound("内战不存在")
		}
		if sc.Status != StatusPublished {
			return refuse("只有已发布的内战可以通知报名的人。")
		}
		people, err := s.participants(txCtx, tx, id)
		if err != nil {
			return err
		}
		count = len(people)
		if err := s.send(txCtx, tx, ctx, s.updateLetter(sc, note), people, now); err != nil {
			return err
		}
		_, err = tx.ExecContext(txCtx, `UPDATE scrims SET moved_from = NULL WHERE id = ?`, id)
		return err
	})
	return count, err
}

// participants 所有活跃且有邮箱的报名者。
func (s *Service) participants(ctx context.Context, q db.DBTX, scrimID int64) ([]mail.Person, error) {
	rows, err := q.QueryContext(ctx, `SELECT u.nickname, u.email FROM scrim_signups g JOIN users u ON u.id = g.user_id
		WHERE g.scrim_id = ? AND u.is_active = 1 AND u.email <> '' ORDER BY g.created_at, g.id`, scrimID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []mail.Person
	for rows.Next() {
		var p mail.Person
		if err := rows.Scan(&p.Name, &p.Address); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func (s *Service) updateLetter(sc *Scrim, note string) mail.Letter {
	moved := sc.MovedFrom != nil && sc.StartsAt != nil && !sc.MovedFrom.Equal(*sc.StartsAt)
	var lead string
	if moved {
		lead = fmt.Sprintf("内战「%s」的开始时间改了：原来 %s，现在 %s。", sc.Title, moment(*sc.MovedFrom), moment(*sc.StartsAt))
	} else {
		lead = fmt.Sprintf("内战「%s」的信息有更新，请以活动页面上的为准。", sc.Title)
	}
	var paragraphs []string
	if note != "" {
		paragraphs = append(paragraphs, "管理员的说明："+note)
	}
	if moved {
		paragraphs = append(paragraphs, "开始前会按新的时间再提醒一次。新时间来不了的话，请取消报名或告诉管理员。")
	}
	when := "时间未定"
	if sc.StartsAt != nil {
		when = moment(*sc.StartsAt)
	}
	return mail.Letter{
		Subject:    "内战有更新：" + sc.Title,
		Lead:       lead,
		Facts:      [][2]string{{"开始时间", when}, {"规格", FormatLabels[sc.Format]}},
		Paragraphs: paragraphs,
		Action:     []string{"查看活动页面", s.scrimURL(sc.ID)},
		Reason:     fmt.Sprintf("你收到这封邮件，是因为你报名了内战「%s」。", sc.Title),
	}
}

func reminderHours(ctx context.Context, q db.DBTX) time.Duration {
	h := 2
	var v int
	if err := q.QueryRowContext(ctx, `SELECT scrim_reminder_hours FROM site_settings WHERE id = 1`).Scan(&v); err == nil && v > 0 {
		h = v
	}
	return time.Duration(h) * time.Hour
}

// Tick 由 worker 每 30 秒跑一次：开始后 6 小时自动结束（规则 147）、开赛前提醒（规则 151）。
func (s *Service) Tick(ctx context.Context, now time.Time) error {
	if err := s.AutoFinish(ctx, now); err != nil {
		return err
	}
	_, err := s.SendDueReminders(ctx, now)
	return err
}

// AutoFinish 已发布的内战开始 6 小时后自动结束；未发布的不动，时间后移自然顺延（规则 147）。
func (s *Service) AutoFinish(ctx context.Context, now time.Time) error {
	cutoff := db.FormatUTC(now.Add(-FinishAfter))
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT id FROM scrims WHERE status = 'published' AND starts_at IS NOT NULL AND starts_at <= ?`, cutoff)
	if err != nil {
		return err
	}
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return err
		}
		ids = append(ids, id)
	}
	rows.Close()
	for _, id := range ids {
		err := s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			sc, err := GetScrim(txCtx, tx, id)
			if err != nil || sc == nil || sc.Status != StatusPublished || sc.StartsAt == nil || now.Before(sc.StartsAt.Add(FinishAfter)) {
				return err
			}
			_, err = tx.ExecContext(txCtx, `UPDATE scrims SET status = 'finished', version = version + 1, updated_at = ? WHERE id = ?`, db.FormatUTC(now), id)
			return err
		})
		if err != nil {
			return err
		}
	}
	return nil
}

// SendDueReminders 开赛前 2 小时（全站设置可配）每位报名者一封，含本人分队去向和社团 QQ 群链接，
// 一场一次；落在窗口内刚保存的至少再等 10 分钟（规则 151、139）。返回发出的信数。
func (s *Service) SendDueReminders(ctx context.Context, now time.Time) (int, error) {
	rd := s.d.ReadPool()
	offset := reminderHours(ctx, rd)
	rows, err := rd.QueryContext(ctx, `SELECT id FROM scrims WHERE status = 'published' AND starts_at IS NOT NULL AND reminder_sent_at IS NULL`)
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
	total := 0
	for _, id := range ids {
		sent := 0
		err := s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			sc, err := GetScrim(txCtx, tx, id)
			if err != nil {
				return err
			}
			if sc == nil || sc.Status != StatusPublished || sc.StartsAt == nil || sc.ReminderSentAt != nil ||
				!now.Before(*sc.StartsAt) || now.Before(sc.StartsAt.Add(-offset)) || now.Before(sc.UpdatedAt.Add(ReminderGrace)) {
				return nil
			}
			var group string
			_ = tx.QueryRowContext(txCtx, `SELECT qq_group_url FROM site_settings WHERE id = 1`).Scan(&group)
			signups, err := listSignups(txCtx, tx, id)
			if err != nil {
				return err
			}
			hasSplit := false
			for _, g := range signups {
				if g.Team != "" {
					hasSplit = true
				}
			}
			for _, g := range signups {
				var nick, email string
				var active int
				if err := tx.QueryRowContext(txCtx, `SELECT nickname, email, is_active FROM users WHERE id = ?`, g.UserID).Scan(&nick, &email, &active); err != nil {
					return err
				}
				if active != 1 || email == "" {
					continue
				}
				facts := [][2]string{{"开始时间", moment(*sc.StartsAt)}, {"规格", FormatLabels[sc.Format]}}
				if p := PlacementText(sc, g, hasSplit); p != "" {
					facts = append(facts, [2]string{"你的分队", p + "（以群里发的为准）"})
				}
				if group != "" {
					facts = append(facts, [2]string{"社团 QQ 群", group})
				}
				if err := s.send(txCtx, tx, nil, mail.Letter{
					Subject:    "内战提醒：" + sc.Title,
					Lead:       fmt.Sprintf("内战「%s」就要开始了，请提前上线。", sc.Title),
					Facts:      facts,
					Paragraphs: []string{"分队结果由管理员发到群里。临时来不了的话，请尽早告诉管理员。"},
					Action:     []string{"查看活动页面", s.scrimURL(id)},
					Reason:     fmt.Sprintf("你收到这封邮件，是因为你报名了内战「%s」。", sc.Title),
				}, []mail.Person{{Address: email, Name: nick}}, now); err != nil {
					return err
				}
				sent++
			}
			_, err = tx.ExecContext(txCtx, `UPDATE scrims SET reminder_sent_at = ? WHERE id = ? AND reminder_sent_at IS NULL`, db.FormatUTC(now), id)
			return err
		})
		if err != nil {
			slog.Warn("内战提醒失败", "id", id, "err", err.Error())
			return total, err
		}
		total += sent
	}
	return total, nil
}

// PlacementText 玩家自己的去向（规则 166）：「A 队 · 坦克」「替补」「这次没排上场」，没有分队时为空。
func PlacementText(sc *Scrim, g *Signup, hasSplit bool) string {
	if !hasSplit {
		return ""
	}
	if g.Team == "a" || g.Team == "b" {
		text := "A 队"
		if g.Team == "b" {
			text = "B 队"
		}
		if sc.RoleQueue() && g.AssignedRole != "" {
			text += " · " + RoleLabels[g.AssignedRole]
		}
		return text
	}
	if g.IsSelected {
		return "替补"
	}
	return "这次没排上场"
}

var _ = sql.ErrNoRows
