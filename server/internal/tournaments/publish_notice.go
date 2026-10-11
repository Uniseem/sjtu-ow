package tournaments

import (
	"context"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/notify"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// SetNotifier connects publication's optional, explicitly confirmed announcement.
func (s *Service) SetNotifier(notifier *notify.Service) { s.notifier = notifier }

type PublishNoticeIn struct {
	ID             api.ID `path:"id"`
	Announce       bool   `json:"announce"`
	PreviewVersion string `json:"preview_version"`
}

type PublishNoticeOut struct {
	Tournament *Tournament    `json:"tournament"`
	Notice     *notify.Result `json:"notice,omitempty"`
}

func (m *Module) publishPreview(ctx *app.Ctx, in IDIn) (*notify.NoticePreview, error) {
	detail, err := m.svc.AdminGet(ctx, int64(in.ID))
	if err != nil {
		return nil, err
	}
	if m.svc.notifier == nil {
		return nil, api.NewErr(503, "unavailable", "暂时无法预览通知。")
	}
	preview, err := m.svc.notifier.PreviewAfterPublish(ctx, notify.KindTournament, int64(in.ID))
	if err != nil {
		return nil, err
	}
	if detail.Tournament.Status != StatusDraft {
		preview.Problem = "只有草稿可以在这里发布。"
	}
	if len(detail.Missing) > 0 {
		preview.Problem = "还没填好：" + strings.Join(detail.Missing, "、") + "。填好再发布。"
	}
	return preview, nil
}

func (m *Module) publishNotice(ctx *app.Ctx, in PublishNoticeIn) (*PublishNoticeOut, error) {
	if !in.Announce {
		item, err := m.svc.Publish(ctx, int64(in.ID))
		return &PublishNoticeOut{Tournament: item}, err
	}
	if m.svc.notifier == nil {
		return nil, api.NewErr(503, "unavailable", "暂时无法发送通知。")
	}
	var notice *notify.Result
	item, err := m.svc.transition(ctx, int64(in.ID), func(t *Tournament, _ time.Time, tx *db.Tx, txCtx context.Context) (string, error) {
		if t.Status != StatusDraft {
			return "", refuse("只有草稿可以在这里发布。")
		}
		if missing := Missing(t); len(missing) > 0 {
			return "", refuse("还没填好：" + strings.Join(missing, "、") + "。填好再发布。")
		}
		var err error
		notice, err = m.svc.notifier.SendAfterPublish(ctx, txCtx, tx, notify.KindTournament, t.ID, in.PreviewVersion)
		if err != nil {
			return "", err
		}
		return StatusPublished, nil
	})
	if err != nil {
		return nil, err
	}
	return &PublishNoticeOut{Tournament: item, Notice: notice}, nil
}
