package notify

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
)

// ParticipantDraft lets each activity supply its own recipients and exact
// activity-specific letter. The shared notifier never imports activity domains.
type ParticipantDraft struct {
	Letter  mail.Letter
	People  []mail.Person
	Problem string
}

// NoticePreview is tied to the actor, object, audience, recipients and body.
// A send may proceed only if the signed digest still describes the same draft.
type NoticePreview struct {
	StartsAt    *time.Time `json:"starts_at"`
	MovedFrom   *time.Time `json:"moved_from"`
	ObjectTitle string     `json:"object_title"`
	SJTUOnly    bool       `json:"sjtu_only"`
	Status
	Audience       string `json:"audience"`
	Subject        string `json:"subject"`
	BodyText       string `json:"body_text"`
	BodyHTML       string `json:"body_html"`
	PreviewVersion string `json:"preview_version"`
	NoteMax        int    `json:"note_max"`
	PreviewURL     string `json:"preview_url"`
}

type noticeDraft struct {
	preview NoticePreview
	letter  mail.Letter
	people  []mail.Person
	subject *Subject
	before  int
	note    string
}

// HistoryCounts supports activity lists in one query, rather than one read per
// object. Keys preserve the existing broadcast audience names.
func HistoryCounts(ctx context.Context, q db.DBTX, kind string) (map[int64]map[string]int, error) {
	rows, err := q.QueryContext(ctx, `SELECT object_id, audience, COUNT(*) FROM broadcasts
		WHERE kind = ? AND waits_for_publish = 0 GROUP BY object_id, audience`, kind)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	counts := map[int64]map[string]int{}
	for rows.Next() {
		var id int64
		var audience string
		var count int
		if err := rows.Scan(&id, &audience, &count); err != nil {
			return nil, err
		}
		if counts[id] == nil {
			counts[id] = map[string]int{}
		}
		counts[id][audience] = count
	}
	return counts, rows.Err()
}

func normalizedAudience(value string) (string, error) {
	switch value {
	case "", "all", Everyone:
		return "all", nil
	case Participants:
		return Participants, nil
	default:
		return "", api.InvalidFields(map[string][]string{"audience": {"收件人范围不对。"}})
	}
}

func (s *Service) makeNoticeDraft(ctx *app.Ctx, q db.DBTX, kind string, id int64, audience, note string, expires int64, publishing ...bool) (*noticeDraft, error) {
	k, err := s.kindFor(kind)
	if err != nil {
		return nil, err
	}
	if err := s.require(ctx, k); err != nil {
		return nil, err
	}
	audience, err = normalizedAudience(audience)
	if err != nil {
		return nil, err
	}
	note = strings.TrimSpace(note)
	if utf8.RuneCountInString(note) > NoteMax {
		return nil, api.InvalidFields(map[string][]string{"note": {fmt.Sprintf("说明最多 %d 字。", NoteMax)}})
	}
	if audience == "all" && note != "" {
		return nil, api.InvalidFields(map[string][]string{"note": {"通知全体成员不使用管理员说明。"}})
	}
	subject, err := k.Load(ctx.Context, q, id)
	if err != nil {
		return nil, err
	}
	if subject == nil {
		return nil, api.NotFound("内容不存在")
	}
	isPublishing := len(publishing) > 0 && publishing[0]
	if isPublishing {
		copy := *subject
		copy.Live = true
		copy.GoLiveAt = nil
		subject = &copy
	}
	now := ctx.Now().UTC()
	draft := &noticeDraft{subject: subject, note: note}
	draft.preview.ObjectTitle = subject.Title
	draft.preview.SJTUOnly = subject.SJTUOnly
	if audience == Participants {
		draft.preview.StartsAt = subject.StartsAt
		draft.preview.MovedFrom = subject.MovedFrom
	}
	draft.preview.Audience = audience
	draft.preview.NoteMax = NoteMax
	if audience == Participants {
		if k.Participants == nil {
			return nil, api.NotFound("这类内容没有参与者通知")
		}
		participation, err := k.Participants(ctx.Context, q, id, note, now)
		if err != nil {
			return nil, err
		}
		draft.letter, draft.people = participation.Letter, mail.People(participation.People)
		draft.preview.Problem = participation.Problem
		if s.mailReady != nil && !s.mailReady() && draft.preview.Problem == "" {
			draft.preview.Problem = "还没有配置邮件（全站设置里的 SMTP），发不出去。"
		}
	} else {
		draft.preview.Problem, err = s.problem(ctx.Context, q, kind, id, subject, now)
		if err != nil {
			return nil, err
		}
		people, err := recipients(ctx.Context, q, subject.SJTUOnly)
		if err != nil {
			return nil, err
		}
		for _, person := range people {
			draft.people = append(draft.people, mail.Person{Address: person.email, Name: person.name})
		}
		draft.letter, err = k.Letter(ctx.Context, q, id, "", now)
		if err != nil {
			return nil, err
		}
		draft.preview.WillWait = !subject.Live && subject.GoLiveAt != nil
	}
	draft.before, err = countBefore(ctx.Context, q, kind, id)
	if err != nil {
		return nil, err
	}
	draft.letter.Notice = RepeatNotice(k.Noun, subject.Title, draft.before)
	draft.preview.Recipients = len(draft.people)
	draft.preview.Subject = draft.letter.Subject
	draft.preview.History, err = history(ctx.Context, q, kind, id)
	if err != nil {
		return nil, err
	}
	var name string
	if err := q.QueryRowContext(ctx.Context, `SELECT nickname FROM users WHERE id = ?`, ctx.Viewer.ID).Scan(&name); err != nil {
		return nil, err
	}
	personal := draft.letter
	if audience == "all" {
		personal.Unsubscribe = s.UnsubscribeURL(ctx.Viewer.ID)
	}
	draft.preview.BodyText = personal.Text(name, s.siteURL, now)
	draft.preview.BodyHTML, err = personal.HTML(name, s.siteURL, now)
	if err != nil {
		return nil, err
	}
	// Do not expose the recipient addresses in the token. They enter only the
	// authenticated digest, so a changed recipient set invalidates confirmation.
	payload, err := json.Marshal(struct {
		Actor      int64
		Kind       string
		ID         int64
		Audience   string
		Note       string
		Letter     mail.Letter
		People     []mail.Person
		Before     int
		Waiting    bool
		Day        string
		Expires    int64
		Publishing bool
	}{ctx.Viewer.ID, kind, id, audience, note, draft.letter, draft.people, draft.before,
		draft.preview.WillWait, now.In(shanghai).Format("2006-01-02"), expires, isPublishing})
	if err != nil {
		return nil, err
	}
	mac := hmac.New(sha256.New, []byte(s.signingKey))
	_, _ = mac.Write(payload)
	draft.preview.PreviewVersion = strconv.FormatInt(expires, 10) + "." + hex.EncodeToString(mac.Sum(nil))
	draft.preview.PreviewURL = noticePreviewURL(kind, id, audience, note, draft.preview.PreviewVersion, isPublishing)
	return draft, nil
}

// PreviewNotice reads a consistent snapshot and does not create a broadcast.
func (s *Service) PreviewNotice(ctx *app.Ctx, kind string, id int64, audience, note string) (*NoticePreview, error) {
	q, err := s.d.ReadPool().BeginTx(ctx.Context, nil)
	if err != nil {
		return nil, err
	}
	defer q.Rollback()
	draft, err := s.makeNoticeDraft(ctx, q, kind, id, audience, note, ctx.Now().Add(15*time.Minute).Unix())
	if err != nil {
		return nil, err
	}
	return &draft.preview, nil
}

// SendPreviewed revalidates and freezes the exact confirmed letters in one
// write transaction. Explicit confirmation sends directly to the outbox;
// ordinary lifecycle writes still use the existing held-letter confirmation.
func (s *Service) SendPreviewed(ctx *app.Ctx, kind string, id int64, audience, note, version string) (*Result, error) {
	parts := strings.Split(version, ".")
	if len(parts) != 2 {
		return nil, api.NewErr(409, "stale_preview", "通知预览已失效，请重新打开预览。")
	}
	expires, err := strconv.ParseInt(parts[0], 10, 64)
	if err != nil || expires <= ctx.Now().Unix() || expires > ctx.Now().Add(15*time.Minute).Unix() {
		return nil, api.NewErr(409, "stale_preview", "通知预览已失效，请重新打开预览。")
	}
	var result Result
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		return s.sendNoticeTx(ctx, txCtx, tx, kind, id, audience, note, version, expires, false, &result)
	})
	if err != nil {
		return nil, err
	}
	return &result, nil
}

func (s *Service) sendNoticeTx(ctx *app.Ctx, txCtx context.Context, tx *db.Tx, kind string, id int64,
	audience, note, version string, expires int64, publishing bool, result *Result) error {
	snapshot := *ctx
	snapshot.Context = txCtx
	draft, err := s.makeNoticeDraft(&snapshot, tx, kind, id, audience, note, expires, publishing)
	if err != nil {
		return err
	}
	if !hmac.Equal([]byte(draft.preview.PreviewVersion), []byte(version)) {
		return api.NewErr(409, "stale_preview", "通知内容或收件人有变化，请重新打开预览。")
	}
	if draft.preview.Problem != "" {
		return refuse(draft.preview.Problem)
	}
	if len(draft.people) == 0 {
		return refuse("没有可收信的人。")
	}
	storedAudience := Everyone
	if draft.preview.Audience == Participants {
		storedAudience = Participants
	}
	waiting := 0
	if draft.preview.WillWait {
		waiting = 1
	}
	now := ctx.Now().UTC()
	deliveredRecipients := len(draft.people)
	if draft.preview.WillWait {
		deliveredRecipients = 0
	}
	row, err := tx.ExecContext(txCtx, `INSERT INTO broadcasts
			(kind, object_id, audience, before_count, note, subject, sent_by, recipient_count, waits_for_publish, created_at)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`, kind, id, storedAudience, draft.before,
		draft.note, draft.letter.Subject, ctx.Viewer.ID, deliveredRecipients, waiting, db.FormatUTC(now))
	if err != nil {
		return err
	}
	broadcastID, err := row.LastInsertId()
	if err != nil {
		return err
	}
	if !draft.preview.WillWait {
		for _, person := range draft.people {
			letter := draft.letter
			if storedAudience == Everyone {
				var userID int64
				if err := tx.QueryRowContext(txCtx, `SELECT id FROM users WHERE email = ?`, person.Address).Scan(&userID); err != nil {
					return err
				}
				letter.Unsubscribe = s.UnsubscribeURL(userID)
			}
			if _, err := outbox.Send(txCtx, tx, nil, s.siteURL, letter, []mail.Person{person}, now); err != nil {
				return err
			}
		}
	}
	if !draft.preview.WillWait {
		if _, err := tx.ExecContext(txCtx, `UPDATE broadcasts SET delivered_at=? WHERE id=?`, db.FormatUTC(now), broadcastID); err != nil {
			return err
		}
	}
	if storedAudience == Participants {
		k, err := s.kindFor(kind)
		if err != nil {
			return err
		}
		if k.ParticipantsSent != nil {
			if err := k.ParticipantsSent(txCtx, tx, id); err != nil {
				return err
			}
		}
	}
	if err := audit.Record(txCtx, tx, ctx.Viewer.ID, kind+"s.announce", kind, id,
		map[string]any{"recipients": len(draft.people), "audience": storedAudience, "on_publish": draft.preview.WillWait, "before": draft.before}, now); err != nil {
		return err
	}
	*result = Result{BroadcastID: broadcastID, Recipients: len(draft.people), Waiting: draft.preview.WillWait}
	return nil
}

// PreviewAfterPublish is a real preview for the optional lifecycle checkbox;
// publication and sending will be validated again inside the same write tx.
func (s *Service) PreviewAfterPublish(ctx *app.Ctx, kind string, id int64) (*NoticePreview, error) {
	q, err := s.d.ReadPool().BeginTx(ctx.Context, nil)
	if err != nil {
		return nil, err
	}
	defer q.Rollback()
	draft, err := s.makeNoticeDraft(ctx, q, kind, id, "all", "", ctx.Now().Add(15*time.Minute).Unix(), true)
	if err != nil {
		return nil, err
	}
	return &draft.preview, nil
}

// SendAfterPublish runs inside the activity's transaction. The activity writer
// remains responsible for checking publishable state and required fields.
func (s *Service) SendAfterPublish(ctx *app.Ctx, txCtx context.Context, tx *db.Tx, kind string, id int64, version string) (*Result, error) {
	parts := strings.Split(version, ".")
	if len(parts) != 2 {
		return nil, api.NewErr(409, "stale_preview", "通知预览已失效，请重新打开发布页。")
	}
	expires, err := strconv.ParseInt(parts[0], 10, 64)
	if err != nil || expires <= ctx.Now().Unix() || expires > ctx.Now().Add(15*time.Minute).Unix() {
		return nil, api.NewErr(409, "stale_preview", "通知预览已失效，请重新打开发布页。")
	}
	var result Result
	if err := s.sendNoticeTx(ctx, txCtx, tx, kind, id, "all", "", version, expires, true, &result); err != nil {
		return nil, err
	}
	return &result, nil
}
