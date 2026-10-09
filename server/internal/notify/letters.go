// Package notify 是 M7 的通知：待发信的确认（设计 10.5）、「通知全体成员」
// 的公告（设计 10.4）、退订。日历订阅在 agenda 包（要读内战和赛事）。
// 这个包不 import 任何业务域：域往这里挂（文章、赛事、内战各交一个 Kind），
// 反过来不依赖，免得绕成圈。
package notify

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
)

// KeepDays 待发信的行留多少天（规则 208：7 天不再问，30 天由清理删掉）。
const KeepDays = 30

// Service 是通知的服务。
type Service struct {
	d          *db.DB
	siteURL    string
	signingKey string
	mailReady  func() bool
	kinds      map[string]Kind
}

// NewService 造通知服务。mailReady 报 SMTP 配没配好（规则 78），nil 当作配好了。
func NewService(d *db.DB, siteURL, signingKey string, mailReady func() bool) *Service {
	return &Service{d: d, siteURL: strings.TrimRight(siteURL, "/"), signingKey: signingKey, mailReady: mailReady, kinds: map[string]Kind{}}
}

// HeldLetter 是确认页上的一封信。
type HeldLetter struct {
	ID      int64  `json:"id"`
	Subject string `json:"subject"`
	Who     string `json:"who"`
	Count   int    `json:"count"`
}

// HeldBatch 是一件事带出来的信。State：waiting 等着、done 已处理、expired 等了 7 天作废。
type HeldBatch struct {
	Batch        string       `json:"batch"`
	State        string       `json:"state"`
	Letters      []HeldLetter `json:"letters"`
	Back         string       `json:"back"`
	InBackOffice bool         `json:"in_back_office"`
}

// WaitingBatch 是还等着的一件事，提醒和列表用。
type WaitingBatch struct {
	Batch        string    `json:"batch"`
	Subjects     []string  `json:"subjects"`
	People       int       `json:"people"`
	At           time.Time `json:"at"`
	InBackOffice bool      `json:"in_back_office"`
}

// DecideResult 是点完「发信」的结果。
type DecideResult struct {
	Letters int `json:"letters"`
	People  int `json:"people"`
}

func login(ctx *app.Ctx) (*app.Viewer, error) {
	v := ctx.Viewer
	if v == nil || v.Disabled || v.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	return v, nil
}

type heldRow struct {
	id         int64
	batch      string
	letter     string
	recipients string
	back       string
	inBack     bool
	state      string
	created    time.Time
}

func scanHeld(rows *sql.Rows) ([]heldRow, error) {
	defer rows.Close()
	var out []heldRow
	for rows.Next() {
		var r heldRow
		var inBack int
		var created string
		if err := rows.Scan(&r.id, &r.batch, &r.letter, &r.recipients, &r.back, &inBack, &r.state, &created); err != nil {
			return nil, err
		}
		r.inBack = inBack == 1
		r.created, _ = db.ParseUTC(created)
		out = append(out, r)
	}
	return out, rows.Err()
}

const heldCols = `id, batch, letter, recipients, back, in_back_office, state, created_at`

// Held 是确认页要看的：这件事冻住的信。别人的批次、不存在的批次都是 404。
func (s *Service) Held(ctx *app.Ctx, batch string) (*HeldBatch, error) {
	v, err := login(ctx)
	if err != nil {
		return nil, err
	}
	rows, err := s.d.ReadPool().QueryContext(ctx.Context, `SELECT `+heldCols+`
		FROM held_letters WHERE batch = ? AND actor_id = ? ORDER BY id`, batch, v.ID)
	if err != nil {
		return nil, err
	}
	all, err := scanHeld(rows)
	if err != nil {
		return nil, err
	}
	if len(all) == 0 {
		return nil, api.NotFound("没有这件事的信")
	}
	out := &HeldBatch{Batch: batch, State: "done", Letters: []HeldLetter{}, Back: all[0].back, InBackOffice: all[0].inBack}
	cutoff := ctx.Now().Add(-outbox.Wait)
	var email string
	_ = s.d.ReadPool().QueryRowContext(ctx.Context, `SELECT email FROM users WHERE id = ?`, v.ID).Scan(&email)
	for _, r := range all {
		if r.state != "waiting" {
			continue
		}
		if r.created.Before(cutoff) {
			out.State = "expired"
			continue
		}
		out.State = "waiting"
		var l mail.Letter
		_ = json.Unmarshal([]byte(r.letter), &l)
		out.Letters = append(out.Letters, HeldLetter{
			ID: r.id, Subject: l.Subject,
			Who: who(parseRecipients(r.recipients), email), Count: len(parseRecipients(r.recipients)),
		})
		out.Back, out.InBackOffice = r.back, r.inBack
	}
	return out, nil
}

// DecideHeld 发勾选的、丢掉这批剩下的。skip 为真什么都不发。每封只认领一次（规则 207、208）。
func (s *Service) DecideHeld(ctx *app.Ctx, batch string, send []int64, skip bool) (*DecideResult, error) {
	v, err := login(ctx)
	if err != nil {
		return nil, err
	}
	if skip {
		send = nil
	}
	var res DecideResult
	var known int
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM held_letters WHERE batch = ? AND actor_id = ?`, batch, v.ID).Scan(&known); err != nil {
			return err
		}
		if known == 0 {
			return nil
		}
		l, p, err := outbox.Decide(txCtx, tx, v.ID, batch, send, false, s.siteURL, ctx.Now())
		res.Letters, res.People = l, p
		return err
	})
	if err != nil {
		return nil, err
	}
	if known == 0 {
		return nil, api.NotFound("没有这件事的信")
	}
	return &res, nil
}

// Waiting 是这个人所有还等着的事（7 天内），新的在前。
func (s *Service) Waiting(ctx *app.Ctx) ([]WaitingBatch, error) {
	v, err := login(ctx)
	if err != nil {
		return nil, err
	}
	rows, err := s.d.ReadPool().QueryContext(ctx.Context, `SELECT `+heldCols+`
		FROM held_letters WHERE actor_id = ? AND state = 'waiting' AND created_at >= ?
		ORDER BY created_at DESC, id`, v.ID, db.FormatUTC(ctx.Now().Add(-outbox.Wait)))
	if err != nil {
		return nil, err
	}
	all, err := scanHeld(rows)
	if err != nil {
		return nil, err
	}
	// 同一批的信是分开的几行，按 batch 合并，顺序按最新一封。
	out := []WaitingBatch{}
	index := map[string]int{}
	for _, r := range all {
		key := r.batch
		i, ok := index[key]
		if !ok {
			index[key] = len(out)
			out = append(out, WaitingBatch{Batch: key, Subjects: []string{}, At: r.created, InBackOffice: r.inBack})
			i = len(out) - 1
		}
		var l mail.Letter
		_ = json.Unmarshal([]byte(r.letter), &l)
		out[i].Subjects = append(out[i].Subjects, l.Subject)
		out[i].People += len(parseRecipients(r.recipients))
	}
	return out, nil
}

// CleanupHeld 删掉 30 天前的待发信行，不管发没发（规则 208）。返回删了几行。
func CleanupHeld(ctx context.Context, tx *db.Tx, now time.Time) (int64, error) {
	res, err := tx.ExecContext(ctx, `DELETE FROM held_letters WHERE created_at < ?`,
		db.FormatUTC(now.Add(-KeepDays*24*time.Hour)))
	if err != nil {
		return 0, err
	}
	return res.RowsAffected()
}

func parseRecipients(raw string) []mail.Person {
	var pairs [][2]string
	if err := json.Unmarshal([]byte(raw), &pairs); err != nil {
		return nil
	}
	out := make([]mail.Person, len(pairs))
	for i, p := range pairs {
		out[i] = mail.Person{Address: p[0], Name: p[1]}
	}
	return out
}

// who 是「你自己」、名字，或「某某等 N 人」（超过 6 人只列前 5 个）。
func who(ps []mail.Person, ownEmail string) string {
	names := make([]string, len(ps))
	for i, p := range ps {
		switch {
		case ownEmail != "" && p.Address == ownEmail:
			names[i] = "你自己"
		case p.Name != "":
			names[i] = p.Name
		default:
			names[i] = p.Address
		}
	}
	if len(names) > 6 {
		return strings.Join(names[:5], "、") + fmt.Sprintf(" 等 %d 人", len(names))
	}
	return strings.Join(names, "、")
}
