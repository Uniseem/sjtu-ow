package tournaments

import (
	"context"
	"database/sql"
	"fmt"
	"log/slog"
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

// ModerationSink 是 AI 内容审核的入口（规则 114）。送审失败只记日志、绝不阻塞操作。
type ModerationSink interface {
	Submit(ctx context.Context, targetType string, targetID int64, field, text, url string, authorID int64) error
}

// Service 协调赛事域的业务规则（设计 8）。
type Service struct {
	d       *db.DB
	siteURL string
	mod     ModerationSink
	viewers ViewerBuilder
}

// NewService 造赛事服务；d 可以是 nil（apigen）。
func NewService(d *db.DB, siteURL string) *Service {
	return &Service{d: d, siteURL: strings.TrimRight(siteURL, "/")}
}

// SetModeration 接上 AI 审核。
func (s *Service) SetModeration(m ModerationSink) { s.mod = m }

func refuse(msg string) *api.Error { return api.NewErr(http.StatusConflict, "refused", msg) }
func deny(msg string) *api.Error   { return api.NewErr(http.StatusForbidden, "forbidden", msg) }

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
	if !v.HasCap(accounts.CapTournamentsManage) {
		return nil, api.Forbidden()
	}
	return v, nil
}

// UserBrief 是信里和名单里要的一个人。
type UserBrief struct {
	ID       int64
	Nickname string
	Email    string
	Active   bool
	IsSJTU   bool
}

func getUser(ctx context.Context, q db.DBTX, id int64) (*UserBrief, error) {
	var u UserBrief
	var active, sjtu int
	err := q.QueryRowContext(ctx, `SELECT id, nickname, email, is_active, is_sjtu FROM users WHERE id = ?`, id).
		Scan(&u.ID, &u.Nickname, &u.Email, &active, &sjtu)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	u.Active, u.IsSJTU = active == 1, sjtu == 1
	return &u, nil
}

func person(u *UserBrief) mail.Person { return mail.Person{Address: u.Email, Name: u.Nickname} }

func (s *Service) url(path string) string { return s.siteURL + path }

func (s *Service) tournamentURL(id int64) string { return s.url(fmt.Sprintf("/tournaments/%d/", id)) }

func (s *Service) send(ctx context.Context, tx *db.Tx, c *app.Ctx, l mail.Letter, to []mail.Person, now time.Time) error {
	var batch *app.LetterBatch
	if c != nil {
		batch = c.Letters
	}
	_, err := outbox.Send(ctx, tx, batch, s.siteURL, l, to, now)
	return err
}

func (s *Service) submitModeration(ctx context.Context, t *Tournament, authorID int64) {
	if s.mod == nil || t.Description == "" {
		return
	}
	if err := s.mod.Submit(ctx, "tournament_description", t.ID, "description", t.Description,
		fmt.Sprintf("/tournaments/%d/", t.ID), authorID); err != nil {
		slog.Warn("赛事说明送审失败", "id", t.ID, "err", err.Error())
	}
}

// teamMaxMembers 全站战队人数上限（规则 113）。
func teamMaxMembers(ctx context.Context, q db.DBTX) int {
	n := 10
	var v int
	if err := q.QueryRowContext(ctx, `SELECT team_max_members FROM site_settings WHERE id = 1`).Scan(&v); err == nil && v > 0 {
		n = v
	}
	return n
}

func hasRegistrations(ctx context.Context, q db.DBTX, id int64) (bool, error) {
	var n int
	err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM registrations WHERE tournament_id = ?`, id).Scan(&n)
	return n > 0, err
}

// hasEntries 有队报名或有人个人报名（规则 111）。
func hasEntries(ctx context.Context, q db.DBTX, id int64) (bool, error) {
	if ok, err := hasRegistrations(ctx, q, id); ok || err != nil {
		return ok, err
	}
	var n int
	err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM individual_signups WHERE tournament_id = ?`, id).Scan(&n)
	return n > 0, err
}

// Missing 草稿离发布还缺什么（规则 109，设计 13.17）。
func Missing(t *Tournament) []string {
	var gaps []string
	if strings.TrimSpace(t.Title) == "" {
		gaps = append(gaps, "标题")
	}
	if t.RegistrationOpensAt == nil {
		gaps = append(gaps, "报名开始时间")
	}
	if t.RegistrationClosesAt == nil {
		gaps = append(gaps, "报名截止时间")
	}
	if t.RegistrationOpensAt != nil && t.RegistrationClosesAt != nil && !t.RegistrationOpensAt.Before(*t.RegistrationClosesAt) {
		gaps = append(gaps, "晚于报名开始的报名截止时间")
	}
	return gaps
}

// CreateTournament 建一个空白草稿（赛事从第一次改动起就存在，设计 13.17）。
func (s *Service) CreateTournament(ctx *app.Ctx) (*Tournament, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	now := db.FormatUTC(ctx.Now().UTC())
	var t *Tournament
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `INSERT INTO tournaments (created_by, version, created_at, updated_at)
			VALUES (?, 1, ?, ?)`, v.ID, now, now)
		if err != nil {
			return err
		}
		id, err := res.LastInsertId()
		if err != nil {
			return err
		}
		t, err = GetTournament(txCtx, tx, id)
		return err
	})
	return t, err
}

// Changes 是这次要改的字段，没出现的不动。时间用 RFC3339 文本，空串表示清空。
type Changes struct {
	Title                *string `json:"title,omitempty"`
	Summary              *string `json:"summary,omitempty"`
	Description          *string `json:"description,omitempty"`
	CoverImageID         *int64  `json:"cover_image_id,omitempty"`
	RemoveCover          *bool   `json:"remove_cover,omitempty"`
	StartsAt             *string `json:"starts_at,omitempty"`
	RegistrationOpensAt  *string `json:"registration_opens_at,omitempty"`
	RegistrationClosesAt *string `json:"registration_closes_at,omitempty"`
	RosterMin            *int    `json:"roster_min,omitempty"`
	RosterMax            *int    `json:"roster_max,omitempty"`
	SjtuOnly             *bool   `json:"sjtu_only,omitempty"`
	RegistrationMode     *string `json:"registration_mode,omitempty"`
	AutoApprove          *bool   `json:"auto_approve,omitempty"`
	ParticipantContact   *string `json:"participant_contact,omitempty"`
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

// UpdateTournament 按字段保存：合法的存，不合法的留旧值（规则 111–113）。开始/截止时间是一组，
// 人数下限/上限是一组：组里任一出错整组不存。
func (s *Service) UpdateTournament(ctx *app.Ctx, id, baseVersion int64, ch Changes) (*SaveResult, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	res := &SaveResult{Fields: map[string][]string{}, SavedAt: now}
	var after *Tournament
	var descChanged bool
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		t, err := GetTournament(txCtx, tx, id)
		if err != nil {
			return err
		}
		if t == nil {
			return api.NotFound("赛事不存在")
		}
		if baseVersion != t.Version {
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
			} else if x != t.Title {
				set("title", "title", x)
			}
		}
		if ch.Summary != nil {
			x := strings.TrimSpace(*ch.Summary)
			if utf8.RuneCountInString(x) > 300 {
				bad("summary", "简介最多 300 字。")
			} else if x != t.Summary {
				set("summary", "summary", x)
			}
		}
		if ch.Description != nil && *ch.Description != t.Description {
			set("description", "description", *ch.Description)
			_, plain, _, _, _, _ := markdown.Facts(*ch.Description, s.siteURL, nil)
			sets = append(sets, "description_plain = ?") // 派生列，不算用户改的字段
			args = append(args, plain)
			descChanged = true
		}
		if ch.ParticipantContact != nil {
			x := strings.TrimSpace(*ch.ParticipantContact)
			if utf8.RuneCountInString(x) > 100 {
				bad("participant_contact", "选手联系方式最多 100 字。")
			} else if x != t.ParticipantContact {
				set("participant_contact", "participant_contact", x)
			}
		}
		if ch.SjtuOnly != nil && *ch.SjtuOnly != t.SjtuOnly {
			set("sjtu_only", "sjtu_only", b2i(*ch.SjtuOnly))
		}
		switch {
		case ch.RemoveCover != nil && *ch.RemoveCover && t.CoverImageID != nil:
			set("cover_image_id", "cover_image_id", nil)
		case ch.CoverImageID != nil && (t.CoverImageID == nil || *t.CoverImageID != *ch.CoverImageID):
			var n int
			if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM images WHERE id = ?`, *ch.CoverImageID).Scan(&n); err != nil {
				return err
			}
			if n == 0 {
				bad("cover_image_id", "封面图片不存在。")
			} else {
				set("cover_image_id", "cover_image_id", *ch.CoverImageID)
			}
		}

		// 报名方式（规则 111）：有任何报名后锁死
		mode := t.RegistrationMode
		if ch.RegistrationMode != nil && *ch.RegistrationMode != t.RegistrationMode {
			switch *ch.RegistrationMode {
			case ModeIndividual, ModeTeam:
				locked, err := hasEntries(txCtx, tx, id)
				if err != nil {
					return err
				}
				if locked {
					bad("registration_mode", "已经有人报名，报名方式不能再改。")
				} else {
					mode = *ch.RegistrationMode
					set("registration_mode", "registration_mode", mode)
				}
			default:
				bad("registration_mode", "报名方式只能是个人报名或整队报名。")
			}
		}
		// 自动通过（规则 112）：有任何队报名后锁死
		if ch.AutoApprove != nil && *ch.AutoApprove != t.AutoApprove {
			locked, err := hasRegistrations(txCtx, tx, id)
			if err != nil {
				return err
			}
			if locked {
				bad("auto_approve", "已经有队报名，「报名自动通过」不能再改。")
			} else {
				set("auto_approve", "auto_approve", b2i(*ch.AutoApprove))
			}
		}

		// 人数一组（规则 113）
		if ch.RosterMin != nil || ch.RosterMax != nil {
			min, max := t.RosterMin, t.RosterMax
			if ch.RosterMin != nil {
				min = *ch.RosterMin
			}
			if ch.RosterMax != nil {
				max = *ch.RosterMax
			}
			var msgs [][2]string
			if min < 1 {
				msgs = append(msgs, [2]string{"roster_min", "参赛人数下限至少 1 人。"})
			}
			if max > 20 {
				msgs = append(msgs, [2]string{"roster_max", "参赛人数上限最多 20 人。"})
			}
			if min > max {
				msgs = append(msgs, [2]string{"roster_max", "参赛人数上限不能小于下限。"})
			}
			if mode == ModeTeam {
				if tm := teamMaxMembers(txCtx, tx); min > tm {
					msgs = append(msgs, [2]string{"roster_min", fmt.Sprintf("参赛人数下限 %d 大于全站战队人数上限 %d，没有战队能满足这个要求。", min, tm)})
				}
			}
			if len(msgs) > 0 {
				for _, m := range msgs {
					bad(m[0], m[1])
				}
			} else {
				if min != t.RosterMin {
					set("roster_min", "roster_min", min)
				}
				if max != t.RosterMax {
					set("roster_max", "roster_max", max)
				}
			}
		}

		// 时间：开始报名/截止一组；比赛时间单独
		var newStarts = t.StartsAt
		startsChanged := false
		if ch.StartsAt != nil {
			p, ok := parseWhen(*ch.StartsAt)
			if !ok {
				bad("starts_at", "时间格式不对。")
			} else if !sameTime(p, t.StartsAt) {
				set("starts_at", "starts_at", timeArg(p))
				newStarts, startsChanged = p, true
			}
		}
		if ch.RegistrationOpensAt != nil || ch.RegistrationClosesAt != nil {
			opens, closes := t.RegistrationOpensAt, t.RegistrationClosesAt
			okAll := true
			if ch.RegistrationOpensAt != nil {
				p, ok := parseWhen(*ch.RegistrationOpensAt)
				if !ok {
					bad("registration_opens_at", "时间格式不对。")
					okAll = false
				}
				opens = p
			}
			if ch.RegistrationClosesAt != nil {
				p, ok := parseWhen(*ch.RegistrationClosesAt)
				if !ok {
					bad("registration_closes_at", "时间格式不对。")
					okAll = false
				}
				closes = p
			}
			if okAll && opens != nil && closes != nil && !opens.Before(*closes) {
				bad("registration_closes_at", "报名截止时间要晚于报名开始时间。")
				okAll = false
			}
			if okAll {
				if ch.RegistrationOpensAt != nil && !sameTime(opens, t.RegistrationOpensAt) {
					set("registration_opens_at", "registration_opens_at", timeArg(opens))
				}
				if ch.RegistrationClosesAt != nil && !sameTime(closes, t.RegistrationClosesAt) {
					set("registration_closes_at", "registration_closes_at", timeArg(closes))
				}
			}
		}

		// 改期（规则 136）：已发布、新时间在未来且变了才触发
		if startsChanged && t.Status == StatusPublished && t.StartsAt != nil && newStarts != nil && newStarts.After(now) {
			told := t.MovedFrom
			if told == nil {
				told = t.StartsAt
			}
			var movedFrom any
			if !told.Equal(*newStarts) {
				movedFrom = db.FormatUTC(*told)
			}
			sets = append(sets, "reminder_sent_at = NULL", "moved_from = ?")
			args = append(args, movedFrom)
		}

		res.Version = t.Version
		if len(sets) > 0 {
			sets = append(sets, "version = version + 1", "updated_at = ?")
			args = append(args, db.FormatUTC(now), id)
			if _, err := tx.ExecContext(txCtx, `UPDATE tournaments SET `+strings.Join(sets, ", ")+` WHERE id = ?`, args...); err != nil {
				return err
			}
			res.Version = t.Version + 1
		}
		after, err = GetTournament(txCtx, tx, id)
		return err
	})
	if err != nil {
		return nil, err
	}
	if len(res.Fields) == 0 {
		res.Fields = nil
	}
	if descChanged && after != nil {
		s.submitModeration(ctx.Context, after, v.ID)
	}
	return res, nil
}

// setStatus 是发布、结束、取消共用的收尾。
func (s *Service) transition(ctx *app.Ctx, id int64, fn func(t *Tournament, now time.Time, tx *db.Tx, txCtx context.Context) (string, error)) (*Tournament, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	var out *Tournament
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		t, err := GetTournament(txCtx, tx, id)
		if err != nil {
			return err
		}
		if t == nil {
			return api.NotFound("赛事不存在")
		}
		status, err := fn(t, now, tx, txCtx)
		if err != nil {
			return err
		}
		if status != "" {
			if _, err := tx.ExecContext(txCtx, `UPDATE tournaments SET status = ?,
				published_at = CASE WHEN ? = 'published' AND published_at IS NULL THEN ? ELSE published_at END,
				version = version + 1, updated_at = ? WHERE id = ?`,
				status, status, db.FormatUTC(now), db.FormatUTC(now), id); err != nil {
				return err
			}
		}
		out, err = GetTournament(txCtx, tx, id)
		return err
	})
	if err != nil {
		return nil, err
	}
	s.submitModeration(ctx.Context, out, v.ID)
	return out, nil
}

// Publish 发布（规则 109、110）：已取消的不能发布，缺东西的不能发布。
func (s *Service) Publish(ctx *app.Ctx, id int64) (*Tournament, error) {
	return s.transition(ctx, id, func(t *Tournament, _ time.Time, _ *db.Tx, _ context.Context) (string, error) {
		if t.Status == StatusCancelled {
			return "", refuse("已取消的赛事不能再发布。")
		}
		if gaps := Missing(t); len(gaps) > 0 {
			return "", refuse("还没填好：" + strings.Join(gaps, "、") + "。填好再发布。")
		}
		return StatusPublished, nil
	})
}

// Finish 标记已结束（规则 110）：只有已发布的。
func (s *Service) Finish(ctx *app.Ctx, id int64) (*Tournament, error) {
	return s.transition(ctx, id, func(t *Tournament, _ time.Time, _ *db.Tx, _ context.Context) (string, error) {
		if t.Status != StatusPublished {
			return "", refuse("只有已发布的赛事可以标记为已结束。")
		}
		return StatusFinished, nil
	})
}

// Cancel 取消（规则 110、141）：没填好的草稿直接删除；每个活跃报名的队长收到取消邮件，
// 临时队伍通知全员。
func (s *Service) Cancel(ctx *app.Ctx, id int64, reason string) (*Tournament, error) {
	reason = strings.TrimSpace(reason)
	if utf8.RuneCountInString(reason) > NotifyNoteMax {
		return nil, api.InvalidFields(map[string][]string{"reason": {fmt.Sprintf("说明最多 %d 字。", NotifyNoteMax)}})
	}
	return s.transition(ctx, id, func(t *Tournament, now time.Time, tx *db.Tx, txCtx context.Context) (string, error) {
		if t.Status == StatusCancelled {
			return "", refuse("赛事已经取消了。")
		}
		if t.Status == StatusDraft && len(Missing(t)) > 0 {
			return "", refuse("还没填好的草稿不用取消，直接删除。")
		}
		recipients, err := s.cancellationRecipients(txCtx, tx, id)
		if err != nil {
			return "", err
		}
		if err := s.notifyCancelled(txCtx, tx, ctx, t, recipients, reason, now); err != nil {
			return "", err
		}
		return StatusCancelled, nil
	})
}

// DeleteTournament 删除：发布过的只能取消，不能删（规则 110）。
func (s *Service) DeleteTournament(ctx *app.Ctx, id int64) error {
	if _, err := requireManager(ctx); err != nil {
		return err
	}
	return s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		t, err := GetTournament(txCtx, tx, id)
		if err != nil {
			return err
		}
		if t == nil {
			return api.NotFound("赛事不存在")
		}
		if t.PublishedAt != nil || t.Status != StatusDraft {
			return refuse("发布过的赛事只能取消，不能删除。")
		}
		_, err = tx.ExecContext(txCtx, `DELETE FROM tournaments WHERE id = ?`, id)
		return err
	})
}

const week = 7 * 24 * time.Hour

// weeksAhead 复制时三个时间整体平移几个整周，让最早的落到未来；至少一周（规则 143）。
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
	n := now.Sub(*earliest)/week + 1
	return n * week
}

// Copy 复制一项赛事为新草稿（规则 143）：只抄 COPIED_FIELDS，状态、报名、提醒、通知不带。
func (s *Service) Copy(ctx *app.Ctx, id int64) (*Tournament, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	var out *Tournament
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		t, err := GetTournament(txCtx, tx, id)
		if err != nil {
			return err
		}
		if t == nil {
			return api.NotFound("赛事不存在")
		}
		shift := weeksAhead([]*time.Time{t.StartsAt, t.RegistrationOpensAt, t.RegistrationClosesAt}, now)
		move := func(p *time.Time) any {
			if p == nil {
				return nil
			}
			return db.FormatUTC(p.Add(shift))
		}
		res, err := tx.ExecContext(txCtx, `INSERT INTO tournaments
			(title, summary, description, cover_image_id, starts_at, registration_opens_at, registration_closes_at,
			 roster_min, roster_max, sjtu_only, registration_mode, auto_approve, participant_contact,
			 created_by, version, created_at, updated_at)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)`,
			t.Title, t.Summary, t.Description, idArg(t.CoverImageID), move(t.StartsAt), move(t.RegistrationOpensAt),
			move(t.RegistrationClosesAt), t.RosterMin, t.RosterMax, b2i(t.SjtuOnly), t.RegistrationMode,
			b2i(t.AutoApprove), t.ParticipantContact, v.ID, db.FormatUTC(now), db.FormatUTC(now))
		if err != nil {
			return err
		}
		nid, err := res.LastInsertId()
		if err != nil {
			return err
		}
		out, err = GetTournament(txCtx, tx, nid)
		return err
	})
	return out, err
}

// NotifyParticipants 「通知报名的人」（规则 137）：时间移动过写明「原来 X，现在 Y」，可附说明；
// 发出后清 moved_from。
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
		t, err := GetTournament(txCtx, tx, id)
		if err != nil {
			return err
		}
		if t == nil {
			return api.NotFound("赛事不存在")
		}
		if t.Status != StatusPublished {
			return refuse("只有已发布的赛事可以通知报名的人。")
		}
		people, err := s.participants(txCtx, tx, id)
		if err != nil {
			return err
		}
		count = len(people)
		if err := s.send(txCtx, tx, ctx, s.updateLetter(t, t.MovedFrom, note), people, now); err != nil {
			return err
		}
		_, err = tx.ExecContext(txCtx, `UPDATE tournaments SET moved_from = NULL WHERE id = ?`, id)
		return err
	})
	return count, err
}

// participants 所有参赛的人：有效名单和散人池，各一次；停用或没邮箱的不发（规则 137）。
func (s *Service) participants(ctx context.Context, q db.DBTX, tournamentID int64) ([]mail.Person, error) {
	rows, err := q.QueryContext(ctx, `SELECT u.id, u.nickname, u.email FROM users u
		WHERE u.is_active = 1 AND u.email <> '' AND u.id IN (
			SELECT user_id FROM registration_members WHERE tournament_id = ? AND is_active = 1
			UNION SELECT user_id FROM individual_signups WHERE tournament_id = ?)
		ORDER BY u.id`, tournamentID, tournamentID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []mail.Person
	for rows.Next() {
		var id int64
		var p mail.Person
		if err := rows.Scan(&id, &p.Name, &p.Address); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

// cancellationRecipients 取消时谁要收信：每个活跃整队报名的队长，临时队伍的全员（规则 141）。
func (s *Service) cancellationRecipients(ctx context.Context, q db.DBTX, tournamentID int64) ([]mail.Person, error) {
	rows, err := q.QueryContext(ctx, `SELECT u.nickname, u.email FROM users u WHERE u.email <> '' AND u.id IN (
		SELECT m.user_id FROM team_memberships m JOIN registrations r ON r.team_id = m.team_id
			WHERE r.tournament_id = ? AND r.status IN ('pending', 'approved') AND m.role = 'captain'
		UNION SELECT rm.user_id FROM registration_members rm JOIN registrations r ON r.id = rm.registration_id
			WHERE r.tournament_id = ? AND r.team_id IS NULL AND r.status IN ('pending', 'approved'))
		ORDER BY u.id`, tournamentID, tournamentID)
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
