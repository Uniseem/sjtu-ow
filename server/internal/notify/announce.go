package notify

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/jobs"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
)

// 公告的种类和读者。
const (
	KindArticle    = "article"
	KindTournament = "tournament"
	KindScrim      = "scrim"

	Everyone     = "everyone"
	Participants = "participants"

	// EveryoneGap 同一件事对全体的两次通知至少隔这么久（规则 75，210 复核 B11）。
	EveryoneGap = 30 * time.Minute

	// NoteMax 「通知报名的人」的说明上限。
	NoteMax = 500

	// JobDeliver 是把一条公告拆成每人一封的任务。
	JobDeliver = "notify.deliver"
)

var shanghai = time.FixedZone("Asia/Shanghai", 8*3600)

// Subject 是一个种类的对象现在的样子。
type Subject struct {
	Title    string
	Live     bool       // 已发布
	GoLiveAt *time.Time // 文章：安排了定时上线、还没上线时的时间
	SJTUOnly bool       // 只通知交大成员
}

// Kind 是一类能被通知的东西。各域各交一个，notify 不认识它们。
type Kind struct {
	Key  string
	Noun string // 「这场赛事」，第二封起信里用（设计 10.3）
	// CanSend：谁能发。
	CanSend func(*app.Viewer) bool
	// Load 读对象；不存在返回 nil, nil。
	Load func(ctx context.Context, q db.DBTX, id int64) (*Subject, error)
	// Letter 是发给全体的那封信。unsubscribe 是收信人自己的退订链接。
	Letter func(ctx context.Context, q db.DBTX, id int64, unsubscribe string, now time.Time) (mail.Letter, error)
}

// Register 挂上一个种类。
func (s *Service) Register(k Kind) { s.kinds[k.Key] = k }

// HistoryItem 是通知的一条历史。
type HistoryItem struct {
	ID             int64     `json:"id"`
	Audience       string    `json:"audience"`
	Subject        string    `json:"subject"`
	RecipientCount int       `json:"recipient_count"`
	Waiting        bool      `json:"waiting"`
	CreatedAt      time.Time `json:"created_at"`
}

// Status 是「通知全体成员」按钮旁边要显示的：能不能发、为什么不能、发给多少人、以前发过什么。
type Status struct {
	Problem    string        `json:"problem"`
	Recipients int           `json:"recipients"`
	WillWait   bool          `json:"will_wait"`
	History    []HistoryItem `json:"history"`
}

// Result 是发出（或排上）之后的回执。
type Result struct {
	BroadcastID int64 `json:"broadcast_id"`
	Recipients  int   `json:"recipients"`
	Waiting     bool  `json:"waiting"`
}

func refuse(msg string) *api.Error { return api.NewErr(http.StatusConflict, "refused", msg) }

func (s *Service) kindFor(key string) (Kind, error) {
	k, ok := s.kinds[key]
	if !ok {
		return Kind{}, api.NotFound("没有这类内容")
	}
	return k, nil
}

func (s *Service) require(ctx *app.Ctx, k Kind) error {
	v, err := login(ctx)
	if err != nil {
		return err
	}
	if k.CanSend == nil || !k.CanSend(v) {
		return api.Forbidden()
	}
	return nil
}

// recipientsSQL 通知谁：启用、开着活动通知、邮箱验证过（规则 76、212）。
func recipientsSQL(sjtuOnly bool) string {
	q := `SELECT id, nickname, email FROM users
		WHERE is_active = 1 AND accepts_announcements = 1 AND email_verified_at IS NOT NULL AND email <> ''`
	if sjtuOnly {
		q += ` AND is_sjtu = 1`
	}
	return q + ` ORDER BY id`
}

type recipient struct {
	id    int64
	name  string
	email string
}

func recipients(ctx context.Context, q db.DBTX, sjtuOnly bool) ([]recipient, error) {
	rows, err := q.QueryContext(ctx, recipientsSQL(sjtuOnly))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []recipient
	for rows.Next() {
		var r recipient
		if err := rows.Scan(&r.id, &r.name, &r.email); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func history(ctx context.Context, q db.DBTX, kind string, id int64) ([]HistoryItem, error) {
	rows, err := q.QueryContext(ctx, `SELECT id, audience, subject, recipient_count, waits_for_publish, created_at
		FROM broadcasts WHERE kind = ? AND object_id = ? ORDER BY created_at DESC, id DESC`, kind, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []HistoryItem{}
	for rows.Next() {
		var h HistoryItem
		var waiting int
		var created string
		if err := rows.Scan(&h.ID, &h.Audience, &h.Subject, &h.RecipientCount, &waiting, &created); err != nil {
			return nil, err
		}
		h.Waiting = waiting == 1
		h.CreatedAt, _ = db.ParseUTC(created)
		out = append(out, h)
	}
	return out, rows.Err()
}

// problem：现在为什么发不出去；空串表示能发（规则 74、75、78）。
func (s *Service) problem(ctx context.Context, q db.DBTX, kind string, id int64, subj *Subject, now time.Time) (string, error) {
	if !subj.Live && subj.GoLiveAt == nil {
		return "发布之后才能通知全体成员。", nil
	}
	var waiting int
	if err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM broadcasts WHERE kind = ? AND object_id = ? AND waits_for_publish = 1`,
		kind, id).Scan(&waiting); err != nil {
		return "", err
	}
	if waiting > 0 {
		return "已经安排在上线时通知全体成员，到时会发出，不用再安排。", nil
	}
	var recent string
	err := q.QueryRowContext(ctx, `SELECT COALESCE(MAX(created_at), '') FROM broadcasts
		WHERE kind = ? AND object_id = ? AND audience = 'everyone' AND created_at >= ?`,
		kind, id, db.FormatUTC(now.Add(-EveryoneGap))).Scan(&recent)
	if err != nil {
		return "", err
	}
	if recent != "" {
		at, _ := db.ParseUTC(recent)
		return fmt.Sprintf("%s 刚通知过全体成员，%d 分钟内不再发。", at.In(shanghai).Format("15:04"), int(EveryoneGap.Minutes())), nil
	}
	if s.mailReady != nil && !s.mailReady() {
		return "还没有配置邮件（全站设置里的 SMTP），发不出去。", nil
	}
	return "", nil
}

// RepeatNotice 第二封起在信里写「之前已经发过 N 次」（规则 77）。
func RepeatNotice(noun, title string, before int) string {
	if before <= 0 {
		return ""
	}
	return fmt.Sprintf("关于%s「%s」，之前已经发过 %d 次邮件，这次可能有修改，请以这封为准。", noun, title, before)
}

func countBefore(ctx context.Context, q db.DBTX, kind string, id int64) (int, error) {
	var n int
	err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM broadcasts WHERE kind = ? AND object_id = ?`, kind, id).Scan(&n)
	return n, err
}

// Status 给后台页：按钮能不能点、发给多少人、历史。
func (s *Service) Status(ctx *app.Ctx, kind string, id int64) (*Status, error) {
	k, err := s.kindFor(kind)
	if err != nil {
		return nil, err
	}
	if err := s.require(ctx, k); err != nil {
		return nil, err
	}
	q := s.d.ReadPool()
	subj, err := k.Load(ctx.Context, q, id)
	if err != nil {
		return nil, err
	}
	if subj == nil {
		return nil, api.NotFound("内容不存在")
	}
	p, err := s.problem(ctx.Context, q, kind, id, subj, ctx.Now())
	if err != nil {
		return nil, err
	}
	people, err := recipients(ctx.Context, q, subj.SJTUOnly)
	if err != nil {
		return nil, err
	}
	h, err := history(ctx.Context, q, kind, id)
	if err != nil {
		return nil, err
	}
	return &Status{Problem: p, Recipients: len(people), WillWait: !subj.Live && subj.GoLiveAt != nil, History: h}, nil
}

// Announce 「通知全体成员」（规则 73–79）：记一条历史，已上线的马上排下发任务，
// 安排了定时上线的记着、上线那一刻再发。
func (s *Service) Announce(ctx *app.Ctx, kind string, id int64) (*Result, error) {
	k, err := s.kindFor(kind)
	if err != nil {
		return nil, err
	}
	if err := s.require(ctx, k); err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	var res Result
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		subj, err := k.Load(txCtx, tx, id)
		if err != nil {
			return err
		}
		if subj == nil {
			return api.NotFound("内容不存在")
		}
		p, err := s.problem(txCtx, tx, kind, id, subj, now)
		if err != nil {
			return err
		}
		if p != "" {
			return refuse(p)
		}
		before, err := countBefore(txCtx, tx, kind, id)
		if err != nil {
			return err
		}
		waiting := !subj.Live && subj.GoLiveAt != nil
		count := 0
		if !waiting {
			people, err := recipients(txCtx, tx, subj.SJTUOnly)
			if err != nil {
				return err
			}
			count = len(people)
		}
		letter, err := k.Letter(txCtx, tx, id, "", now)
		if err != nil {
			return err
		}
		w := 0
		if waiting {
			w = 1
		}
		r, err := tx.ExecContext(txCtx, `INSERT INTO broadcasts
			(kind, object_id, audience, before_count, note, subject, sent_by, recipient_count, waits_for_publish, created_at)
			VALUES (?, ?, 'everyone', ?, '', ?, ?, ?, ?, ?)`,
			kind, id, before, letter.Subject, ctx.Viewer.ID, count, w, db.FormatUTC(now))
		if err != nil {
			return err
		}
		bid, err := r.LastInsertId()
		if err != nil {
			return err
		}
		if err := audit.Record(txCtx, tx, ctx.Viewer.ID, kind+"s.announce", kind, id,
			map[string]any{"recipients": count, "on_publish": waiting, "before": before}, now); err != nil {
			return err
		}
		if !waiting {
			if err := enqueueDeliver(txCtx, tx, bid, now); err != nil {
				return err
			}
		}
		res = Result{BroadcastID: bid, Recipients: count, Waiting: waiting}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return &res, nil
}

func enqueueDeliver(ctx context.Context, tx *db.Tx, broadcastID int64, now time.Time) error {
	raw, _ := json.Marshal(map[string]int64{"broadcast_id": broadcastID})
	_, err := jobs.Enqueue(ctx, tx, jobs.Job{Kind: JobDeliver, Lane: jobs.LaneDefault, Args: string(raw)}, now)
	return err
}

// SendWaiting 文章上线了：把安排在这一刻的通知放出去（规则 55、74）。
// 认领靠那条条件更新：第二次来什么都找不到。在上线的同一个事务里调。
func SendWaiting(ctx context.Context, tx *db.Tx, kind string, id int64, now time.Time) (bool, error) {
	rows, err := tx.QueryContext(ctx, `UPDATE broadcasts SET waits_for_publish = 0
		WHERE kind = ? AND object_id = ? AND waits_for_publish = 1 RETURNING id`, kind, id)
	if err != nil {
		return false, err
	}
	var ids []int64
	for rows.Next() {
		var bid int64
		if err := rows.Scan(&bid); err != nil {
			_ = rows.Close()
			return false, err
		}
		ids = append(ids, bid)
	}
	err = rows.Err()
	_ = rows.Close()
	if err != nil {
		return false, err
	}
	for _, bid := range ids {
		if err := enqueueDeliver(ctx, tx, bid, now); err != nil {
			return false, err
		}
	}
	return len(ids) > 0, nil
}

// ParticipantsNote 是「通知报名的人」要记的。信本身由赛事、内战自己写、自己发（经待发信）。
type ParticipantsNote struct {
	Kind       string
	ObjectID   int64
	Noun       string
	Title      string
	Subject    string
	Note       string
	Actor      int64
	Recipients int
}

// RecordParticipants 记一条「通知报名的人」的历史，返回信里要写的「之前已经发过 N 次」。
func RecordParticipants(ctx context.Context, tx *db.Tx, n ParticipantsNote, now time.Time) (string, error) {
	before, err := countBefore(ctx, tx, n.Kind, n.ObjectID)
	if err != nil {
		return "", err
	}
	if _, err := tx.ExecContext(ctx, `INSERT INTO broadcasts
		(kind, object_id, audience, before_count, note, subject, sent_by, recipient_count, waits_for_publish, created_at)
		VALUES (?, ?, 'participants', ?, ?, ?, ?, ?, 0, ?)`,
		n.Kind, n.ObjectID, before, n.Note, n.Subject, n.Actor, n.Recipients, db.FormatUTC(now)); err != nil {
		return "", err
	}
	if err := audit.Record(ctx, tx, n.Actor, n.Kind+"s.notify_participants", n.Kind, n.ObjectID,
		map[string]any{"recipients": n.Recipients, "before": before}, now); err != nil {
		return "", err
	}
	return RepeatNotice(n.Noun, n.Title, before), nil
}

// Deliver 是下发任务：发送这一刻才重算收件人，每人一封、各带自己的退订链接（规则 76）。
// 这期间关掉了活动通知的人不发。
func (s *Service) Deliver() jobs.Handler {
	return func(ctx context.Context, d *db.DB, j jobs.Job) error {
		var args struct {
			BroadcastID int64 `json:"broadcast_id"`
		}
		if err := json.Unmarshal([]byte(j.Args), &args); err != nil {
			return err
		}
		return d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			var kind string
			var id int64
			var before int
			err := tx.QueryRowContext(txCtx, `SELECT kind, object_id, before_count FROM broadcasts WHERE id = ?`, args.BroadcastID).
				Scan(&kind, &id, &before)
			if err != nil {
				return nil // 记录没了，没什么可发的
			}
			k, err := s.kindFor(kind)
			if err != nil {
				return nil
			}
			subj, err := k.Load(txCtx, tx, id)
			if err != nil {
				return err
			}
			if subj == nil {
				return nil
			}
			now := time.Now().UTC()
			base, err := k.Letter(txCtx, tx, id, "", now)
			if err != nil {
				return err
			}
			base.Notice = RepeatNotice(k.Noun, subj.Title, before)
			people, err := recipients(txCtx, tx, subj.SJTUOnly)
			if err != nil {
				return err
			}
			sent := 0
			for _, p := range people {
				l := base
				l.Unsubscribe = s.UnsubscribeURL(p.id)
				n, err := outbox.Send(txCtx, tx, nil, s.siteURL, l, []mail.Person{{Address: p.email, Name: p.name}}, now)
				if err != nil {
					return err
				}
				sent += n
			}
			_, err = tx.ExecContext(txCtx, `UPDATE broadcasts SET recipient_count = ? WHERE id = ?`, sent, args.BroadcastID)
			return err
		})
	}
}
