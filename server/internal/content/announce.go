package content

import (
	"context"
	"database/sql"
	"errors"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/notify"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

// AnnounceKind 是文章的「通知全体成员」（规则 73–79）：只有能改作者的人能发；
// 已发布或已安排定时上线才能发，安排了定时的等上线那一刻再发。
func (s *Service) AnnounceKind() notify.Kind {
	return notify.Kind{
		Key:     notify.KindArticle,
		Noun:    "这篇文章",
		CanSend: s.canEditAuthor,
		Load: func(ctx context.Context, q db.DBTX, id int64) (*notify.Subject, error) {
			var title string
			var live int
			var goLive sql.NullString
			err := q.QueryRowContext(ctx, `SELECT title, live, go_live_at FROM pages WHERE id = ? AND kind = 'article'`, id).
				Scan(&title, &live, &goLive)
			if errors.Is(err, sql.ErrNoRows) {
				return nil, nil
			}
			if err != nil {
				return nil, err
			}
			subj := &notify.Subject{Title: title, Live: live == 1}
			if live == 0 && goLive.Valid && goLive.String != "" {
				if t, err := time.Parse(time.RFC3339Nano, goLive.String); err == nil {
					subj.GoLiveAt = &t
				}
			}
			return subj, nil
		},
		Letter: func(ctx context.Context, q db.DBTX, id int64, unsubscribe string, _ time.Time) (mail.Letter, error) {
			var title, slug, summary string
			var category sql.NullString
			err := q.QueryRowContext(ctx, `SELECT p.title, p.slug, a.summary, c.name
				FROM pages p JOIN articles a ON a.page_id = p.id
				LEFT JOIN article_categories c ON c.id = a.category_id
				WHERE p.id = ?`, id).Scan(&title, &slug, &summary, &category)
			if err != nil {
				return mail.Letter{}, err
			}
			kind := "文章"
			if category.Valid && category.String != "" {
				kind = category.String
			}
			var paragraphs []string
			if summary != "" {
				paragraphs = []string{summary}
			}
			return mail.Letter{
				Subject:     kind + "：" + title,
				Lead:        "社团发布了一篇" + kind + "「" + title + "」。",
				Paragraphs:  paragraphs,
				Action:      []string{"阅读全文", s.siteURL + "/news/" + slug + "/"},
				Reason:      "你收到这封邮件，是因为你在社区开着「活动通知」。",
				Unsubscribe: unsubscribe,
			}, nil
		},
	}
}
