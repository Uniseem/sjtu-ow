// Package outbox 是待发信（12 号文档 5.11、设计 10.5）。
// 有批次就冻住，等做事的人点头；没有（worker、命令）就直接进邮件车道。
package outbox

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/jobs"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

// KindLetter 是邮件车道上「发一封信给一个人」的任务。
const KindLetter = "mail.letter"

// Wait 是还能在确认页上看到的时间。过了就不再问。
const Wait = 7 * 24 * time.Hour

type payload struct {
	Letter  mail.Letter `json:"letter"`
	To      mail.Person `json:"to"`
	SiteURL string      `json:"site_url"`
}

// Open 给这次写请求开一个批次。调用方把它放进 app.Ctx.Letters。
func Open(actorID int64) *app.LetterBatch {
	var b [16]byte
	_, _ = rand.Read(b[:])
	return &app.LetterBatch{Key: hex.EncodeToString(b[:]), ActorID: actorID}
}

// Send 冻住或入队。返回这次真正入队的封数（冻住时是 0）。
func Send(ctx context.Context, tx *db.Tx, batch *app.LetterBatch, siteURL string, letter mail.Letter, recipients []mail.Person, now time.Time) (int, error) {
	people := mail.People(recipients)
	if len(people) == 0 {
		return 0, nil
	}
	letter = canon(letter)
	if batch == nil || batch.ActorID == 0 {
		return enqueue(ctx, tx, siteURL, letter, people, now)
	}
	body, err := json.Marshal(letter)
	if err != nil {
		return 0, err
	}
	var existingID int64
	var existingRecipients string
	err = tx.QueryRowContext(ctx, `SELECT id, recipients FROM held_letters
		WHERE batch = ? AND state = 'waiting' AND letter = ?`, batch.Key, string(body)).
		Scan(&existingID, &existingRecipients)
	found := err == nil
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return 0, err
	}
	if found {
		merged := mergeRecipients(existingRecipients, people)
		_, err = tx.ExecContext(ctx, `UPDATE held_letters SET recipients = ? WHERE id = ?`, merged, existingID)
		return 0, err
	}
	_, err = tx.ExecContext(ctx, `INSERT INTO held_letters
		(batch, actor_id, letter, recipients, state, created_at)
		VALUES (?, ?, ?, ?, 'waiting', ?)`,
		batch.Key, batch.ActorID, string(body), recipientsJSON(people), db.FormatUTC(now))
	if err != nil {
		return 0, err
	}
	batch.Held++
	return 0, nil
}

// Decide 发 keep 里点名的、丢掉这批剩下的。每一行只认领一次，第二次点什么都不发。
// anyone 用来在操作人已经注销、没人可问的时候由系统代发。
func Decide(ctx context.Context, tx *db.Tx, actorID int64, batchKey string, keep []int64, anyone bool, siteURL string, now time.Time) (letters, people int, err error) {
	keepSet := map[int64]struct{}{}
	for _, id := range keep {
		keepSet[id] = struct{}{}
	}
	// 不在这里滤掉已决定的行：认领只靠下面那条「还是 waiting 才改」的条件更新。
	// 滤掉的话，把条件更新改坏，测试仍然是绿的。
	q := `SELECT id, letter, recipients, created_at FROM held_letters WHERE batch = ?`
	args := []any{batchKey}
	if !anyone {
		q += ` AND actor_id = ? AND created_at >= ?`
		args = append(args, actorID, db.FormatUTC(now.Add(-Wait)))
	}
	rows, err := tx.QueryContext(ctx, q, args...)
	if err != nil {
		return 0, 0, err
	}
	type row struct {
		id         int64
		letter     string
		recipients string
	}
	var list []row
	for rows.Next() {
		var r row
		var created string
		if err := rows.Scan(&r.id, &r.letter, &r.recipients, &created); err != nil {
			_ = rows.Close()
			return 0, 0, err
		}
		list = append(list, r)
	}
	err = rows.Err()
	_ = rows.Close()
	if err != nil {
		return 0, 0, err
	}
	for _, r := range list {
		state := "skipped"
		if _, ok := keepSet[r.id]; ok {
			state = "sent"
		}
		res, err := tx.ExecContext(ctx, `UPDATE held_letters SET state = ?, decided_at = ?
			WHERE id = ? AND state = 'waiting'`, state, db.FormatUTC(now), r.id)
		if err != nil {
			return letters, people, err
		}
		n, err := res.RowsAffected()
		if err != nil {
			return letters, people, err
		}
		if n == 0 || state != "sent" {
			continue
		}
		var letter mail.Letter
		if err := json.Unmarshal([]byte(r.letter), &letter); err != nil {
			return letters, people, err
		}
		ps := parseRecipients(r.recipients)
		queued, err := enqueue(ctx, tx, siteURL, letter, ps, now)
		if err != nil {
			return letters, people, err
		}
		letters++
		people += queued
	}
	return letters, people, nil
}

// MarkBack 记下做完事本来要去的地址，确认页发完再回去。
func MarkBack(ctx context.Context, tx *db.Tx, batchKey, back string, inBackOffice bool) error {
	flag := 0
	if inBackOffice {
		flag = 1
	}
	if len(back) > 500 {
		back = back[:500]
	}
	_, err := tx.ExecContext(ctx, `UPDATE held_letters SET back = ?, in_back_office = ?
		WHERE batch = ? AND state = 'waiting'`, back, flag, batchKey)
	return err
}

func enqueue(ctx context.Context, tx *db.Tx, siteURL string, letter mail.Letter, people []mail.Person, now time.Time) (int, error) {
	n := 0
	for _, p := range people {
		raw, err := json.Marshal(payload{Letter: letter, To: p, SiteURL: siteURL})
		if err != nil {
			return n, err
		}
		if _, err := jobs.Enqueue(ctx, tx, jobs.Job{
			Kind: KindLetter, Lane: jobs.LaneMail, Args: string(raw),
		}, now); err != nil {
			return n, err
		}
		n++
	}
	return n, nil
}

// Handler 是邮件车道上的处理函数。名单挡下的记成做完，不重试。
func Handler(cfg mail.SMTP) jobs.Handler {
	return func(ctx context.Context, _ *db.DB, j jobs.Job) error {
		var p payload
		if err := json.Unmarshal([]byte(j.Args), &p); err != nil {
			return err
		}
		_, err := mail.Deliver(ctx, cfg, p.Letter, p.To, p.SiteURL, time.Now())
		return err
	}
}

func canon(l mail.Letter) mail.Letter {
	if l.Paragraphs == nil {
		l.Paragraphs = []string{}
	}
	if l.Facts == nil {
		l.Facts = [][2]string{}
	}
	if l.Items == nil {
		l.Items = [][2]string{}
	}
	if len(l.Action) == 0 {
		l.Action = nil
	}
	if l.ItemLink == "" {
		l.ItemLink = "打开"
	}
	return l
}

func recipientsJSON(ps []mail.Person) string {
	pairs := make([][2]string, len(ps))
	for i, p := range ps {
		pairs[i] = [2]string{p.Address, p.Name}
	}
	b, _ := json.Marshal(pairs)
	return string(b)
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

func mergeRecipients(raw string, extra []mail.Person) string {
	have := parseRecipients(raw)
	seen := map[string]struct{}{}
	for _, p := range have {
		seen[p.Address] = struct{}{}
	}
	for _, p := range extra {
		if _, ok := seen[p.Address]; ok {
			continue
		}
		have = append(have, p)
		seen[p.Address] = struct{}{}
	}
	return recipientsJSON(have)
}
