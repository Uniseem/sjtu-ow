package notify

import (
	"context"
	"database/sql"
	"errors"
	"net/http"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/djsign"
)

// UnsubscribeSalt 和现行站一样，信里已经发出去的退订链接换栈后照样能用。
const UnsubscribeSalt = "core.announcements.unsubscribe"

// Prefs 是活动通知的开关。
type Prefs struct {
	Nickname string `json:"nickname,omitempty"`
	Accepts  bool   `json:"accepts"`
}

// Token 是某人的退订令牌。
func (s *Service) Token(userID int64) string {
	t, err := djsign.Dumps(s.signingKey, UnsubscribeSalt, userID)
	if err != nil {
		return ""
	}
	return t
}

// UnsubscribeURL 是信里那个人专属的退订链接（前台页面的地址）。
func (s *Service) UnsubscribeURL(userID int64) string {
	return s.siteURL + "/unsubscribe/" + s.Token(userID) + "/"
}

// userFor 令牌是谁的。被篡改、账号停用或不存在都当没有这个人。
func (s *Service) userFor(ctx context.Context, q db.DBTX, token string) (int64, Prefs, bool) {
	var id int64
	if err := djsign.Loads(s.signingKey, UnsubscribeSalt, token, &id); err != nil || id <= 0 {
		return 0, Prefs{}, false
	}
	var p Prefs
	var accepts int
	err := q.QueryRowContext(ctx, `SELECT nickname, accepts_announcements FROM users WHERE id = ? AND is_active = 1`, id).
		Scan(&p.Nickname, &accepts)
	if errors.Is(err, sql.ErrNoRows) || err != nil {
		return 0, Prefs{}, false
	}
	p.Accepts = accepts == 1
	return id, p, true
}

// UnsubscribeInfo 页面打开时问一下：这是谁的链接、现在开着还是关着。
func (s *Service) UnsubscribeInfo(ctx *app.Ctx, token string) (*Prefs, error) {
	_, p, ok := s.userFor(ctx.Context, s.d.ReadPool(), token)
	if !ok {
		return nil, api.NotFound("这个链接无效")
	}
	return &p, nil
}

// Unsubscribe 关掉这个人的活动通知。幂等：已经关了再点还是关着。
func (s *Service) Unsubscribe(ctx *app.Ctx, token string) (*Prefs, error) {
	var out Prefs
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		id, p, ok := s.userFor(txCtx, tx, token)
		if !ok {
			return api.NotFound("这个链接无效")
		}
		if p.Accepts {
			if _, err := tx.ExecContext(txCtx, `UPDATE users SET accepts_announcements = 0 WHERE id = ?`, id); err != nil {
				return err
			}
		}
		p.Accepts = false
		out = p
		return nil
	})
	if err != nil {
		return nil, err
	}
	return &out, nil
}

// MyPrefs 我自己的开关。
func (s *Service) MyPrefs(ctx *app.Ctx) (*Prefs, error) {
	v, err := login(ctx)
	if err != nil {
		return nil, err
	}
	var accepts int
	if err := s.d.ReadPool().QueryRowContext(ctx.Context, `SELECT accepts_announcements FROM users WHERE id = ?`, v.ID).Scan(&accepts); err != nil {
		return nil, err
	}
	return &Prefs{Accepts: accepts == 1}, nil
}

// SetMyPrefs 打开或关掉我的活动通知。与本人有关的信（报名、申请、提醒）不受它管（规则 213）。
func (s *Service) SetMyPrefs(ctx *app.Ctx, accepts bool) (*Prefs, error) {
	v, err := login(ctx)
	if err != nil {
		return nil, err
	}
	val := 0
	if accepts {
		val = 1
	}
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(txCtx, `UPDATE users SET accepts_announcements = ? WHERE id = ?`, val, v.ID)
		return err
	})
	if err != nil {
		return nil, err
	}
	return &Prefs{Accepts: accepts}, nil
}

// OneClick 是邮件客户端的「一键退订」（RFC 8058）：POST 到信里的链接，没有 CSRF 令牌，
// 地址里的签名就是凭证。地址形如 /unsubscribe/{token}/。
func (s *Service) OneClick(w http.ResponseWriter, r *http.Request) {
	token := strings.TrimSpace(r.PathValue("token"))
	if _, err := s.Unsubscribe(&app.Ctx{Context: r.Context()}, token); err != nil {
		http.Error(w, "这个链接无效", http.StatusNotFound)
		return
	}
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("已退订活动通知\n"))
}
