package notify

import (
	"context"
	"encoding/json"
	"errors"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/jobs"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
)

func TestScheduledNoticeRecordsNoRecipientsBeforePublication(t *testing.T) {
	e := newEnv(t)
	actor := e.editor()
	e.user("收件人")
	later := t0.Add(time.Hour)
	e.subject.GoLiveAt = &later
	e.subject.Live = false
	preview, err := e.svc.PreviewNotice(actor, KindArticle, 7, "all", "")
	if err != nil || !preview.WillWait {
		t.Fatalf("scheduled preview: %+v %v", preview, err)
	}
	result, err := e.svc.SendPreviewed(actor, KindArticle, 7, "all", "", preview.PreviewVersion)
	if err != nil || !result.Waiting {
		t.Fatalf("scheduled send: %+v %v", result, err)
	}
	if e.count(`SELECT COUNT(*) FROM broadcasts WHERE waits_for_publish=1 AND recipient_count=0 AND delivered_at IS NULL`) != 1 {
		t.Fatal("recipients counted before delivery")
	}
	if e.count(`SELECT COUNT(*) FROM jobs WHERE kind=?`, outbox.KindLetter) != 0 {
		t.Fatal("scheduled notice queued mail early")
	}
}

func TestConfirmedNoticeRejectsChangedRecipientsWithoutWriting(t *testing.T) {
	e := newEnv(t)
	actor := e.editor()
	reader := e.user("收件人")
	preview, err := e.svc.PreviewNotice(actor, KindArticle, 7, "all", "")
	if err != nil {
		t.Fatal(err)
	}
	if preview.Recipients != 2 || preview.PreviewVersion == "" || preview.PreviewURL == "" {
		t.Fatalf("incomplete preview: %+v", preview)
	}
	e.exec(`UPDATE users SET accepts_announcements=0 WHERE id=?`, reader)
	_, err = e.svc.SendPreviewed(actor, KindArticle, 7, "all", "", preview.PreviewVersion)
	var stale *api.Error
	if !errors.As(err, &stale) || stale.Status != 409 {
		t.Fatalf("changed audience accepted: %v", err)
	}
	if e.count(`SELECT COUNT(*) FROM broadcasts`) != 0 || e.count(`SELECT COUNT(*) FROM jobs WHERE kind=?`, outbox.KindLetter) != 0 {
		t.Fatal("stale preview wrote broadcasts or letters")
	}
	fresh, err := e.svc.PreviewNotice(actor, KindArticle, 7, "all", "")
	if err != nil {
		t.Fatal(err)
	}
	result, err := e.svc.SendPreviewed(actor, KindArticle, 7, "all", "", fresh.PreviewVersion)
	if err != nil {
		t.Fatal(err)
	}
	if result.Recipients != 1 || e.count(`SELECT COUNT(*) FROM jobs WHERE kind=?`, outbox.KindLetter) != 1 {
		t.Fatalf("confirmed actual audience not frozen: %+v", result)
	}
	if e.count(`SELECT COUNT(*) FROM broadcasts WHERE delivered_at IS NOT NULL`) != 1 {
		t.Fatal("direct confirmed enqueue has no replay marker")
	}
}

func TestConfirmedNoticeRejectsChangedBodyAndActor(t *testing.T) {
	e := newEnv(t)
	actor := e.editor()
	preview, err := e.svc.PreviewNotice(actor, KindArticle, 4, "all", "")
	if err != nil {
		t.Fatal(err)
	}
	e.subject.Title = "另一篇内容"
	if _, err := e.svc.SendPreviewed(actor, KindArticle, 4, "all", "", preview.PreviewVersion); err == nil {
		t.Fatal("changed body was sent using old approval")
	}
	if e.count(`SELECT COUNT(*) FROM jobs WHERE kind=?`, outbox.KindLetter) != 0 {
		t.Fatal("changed body entered outbox")
	}
	e.subject.Title = "秋季招新"
	secondActor := e.user("另一个编辑")
	e.exec(`UPDATE users SET accepts_announcements=0 WHERE id=?`, secondActor)
	another := e.ctxAt(secondActor, t0, capAnnounce)
	if _, err := e.svc.SendPreviewed(another, KindArticle, 4, "all", "", preview.PreviewVersion); err == nil {
		t.Fatal("another actor reused the first actor's approval")
	}
	if e.count(`SELECT COUNT(*) FROM broadcasts`) != 0 {
		t.Fatal("rejected actor wrote a broadcast")
	}
}

func TestWorkerBroadcastReplayDoesNotDuplicateOutbox(t *testing.T) {
	e := newEnv(t)
	actor := e.editor()
	e.user("收件人")
	result, err := e.svc.Announce(actor, KindArticle, 7)
	if err != nil {
		t.Fatal(err)
	}
	payload, _ := json.Marshal(map[string]int64{"broadcast_id": result.BroadcastID})
	job := jobs.Job{Kind: JobDeliver, Args: string(payload)}
	if err := e.svc.Deliver()(context.Background(), e.d, job); err != nil {
		t.Fatal(err)
	}
	count := e.count(`SELECT COUNT(*) FROM jobs WHERE kind=?`, outbox.KindLetter)
	if count != 2 {
		t.Fatalf("first execution scheduled %d letters", count)
	}
	if err := e.svc.Deliver()(context.Background(), e.d, job); err != nil {
		t.Fatal(err)
	}
	if e.count(`SELECT COUNT(*) FROM jobs WHERE kind=?`, outbox.KindLetter) != count {
		t.Fatal("replayed broadcast enqueued duplicate letters")
	}
}
