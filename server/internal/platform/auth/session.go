package auth

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"database/sql"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

const (
	// SessionTTL 登录起 14 天（5.7）。
	SessionTTL = 14 * 24 * time.Hour
	// ReauthWindow 改邮箱要求这段时间内输过密码（设计 v7.19）。
	ReauthWindow = 5 * time.Minute
	// TouchEvery 最后访问时间最多这么久写一次（5.4：GET 唯一允许的写）。
	TouchEvery = time.Hour

	// CookieName 是会话 Cookie 的名字。
	CookieName = "ow_session"
)

// Session 是从库里读出来的一条会话。令牌本身不在这里。
type Session struct {
	UserID    int64
	CreatedAt time.Time
	ExpiresAt time.Time
	ReauthAt  time.Time // 零值表示从没重新认证过
	LastSeen  time.Time
}

// RecentlyReauthed 报告 now 是否落在重新认证后的 5 分钟里。
func (s *Session) RecentlyReauthed(now time.Time) bool {
	if s == nil || s.ReauthAt.IsZero() {
		return false
	}
	return !now.Before(s.ReauthAt) && !now.After(s.ReauthAt.Add(ReauthWindow))
}

// Store 是会话的存储。
type Store struct {
	db    *db.DB
	clock clock.Clock
}

// NewStore 造一个存储。clock 为空就用真时钟。
func NewStore(d *db.DB, c clock.Clock) *Store {
	if c == nil {
		c = clock.System{}
	}
	return &Store{db: d, clock: c}
}

// Create 发一条新会话，返回放进 Cookie 的令牌（32 字节的 base64url）。库里只存 SHA-256。
func (s *Store) Create(ctx context.Context, userID int64) (string, error) {
	return s.CreateWithNotice(ctx, userID, "")
}

// CreateWithNotice 将首次整页显示的提示与新会话一起保存。
func (s *Store) CreateWithNotice(ctx context.Context, userID int64, notice string) (string, error) {
	raw := make([]byte, 32)
	if _, err := rand.Read(raw); err != nil {
		return "", err
	}
	now := s.clock.Now().UTC()
	err := s.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, `INSERT INTO sessions
			(token_hash, user_id, created_at, expires_at, reauth_at, last_seen_at, flash_message)
			VALUES (?, ?, ?, ?, '', ?, ?)`,
			hashToken(raw), userID, db.FormatUTC(now), db.FormatUTC(now.Add(SessionTTL)), db.FormatUTC(now), notice)
		return err
	})
	if err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(raw), nil
}

// Lookup 按 Cookie 里的令牌找会话。没有、令牌坏了、过期了，都是 (nil, nil)。
func (s *Store) Lookup(ctx context.Context, cookie string) (*Session, error) {
	raw, err := base64.RawURLEncoding.DecodeString(cookie)
	if err != nil || len(raw) != 32 {
		return nil, nil
	}
	var userID int64
	var created, expires, reauth, seen string
	err = s.db.ReadPool().QueryRowContext(ctx, `SELECT user_id, created_at, expires_at, reauth_at, last_seen_at
		FROM sessions WHERE token_hash = ?`, hashToken(raw)).
		Scan(&userID, &created, &expires, &reauth, &seen)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	sess, err := scanSession(userID, created, expires, reauth, seen)
	if err != nil {
		return nil, err
	}
	if !s.clock.Now().Before(sess.ExpiresAt) {
		return nil, nil
	}
	return sess, nil
}

// Delete 删掉这一条（退出）。
func (s *Store) Delete(ctx context.Context, cookie string) error {
	raw, err := decodeToken(cookie)
	if err != nil {
		return nil
	}
	return s.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, `DELETE FROM sessions WHERE token_hash = ?`, hashToken(raw))
		return err
	})
}

// DeleteOthersTx 在写事务中执行：删掉这个人除当前这条以外的会话。
func (s *Store) DeleteOthersTx(ctx context.Context, tx *db.Tx, userID int64, keepCookie string) error {
	raw, err := decodeToken(keepCookie)
	if err != nil {
		_, err := tx.ExecContext(ctx, `DELETE FROM sessions WHERE user_id = ?`, userID)
		return err
	}
	keep := hashToken(raw)
	_, err = tx.ExecContext(ctx, `DELETE FROM sessions WHERE user_id = ? AND token_hash <> ?`, userID, keep)
	return err
}

// DeleteOthers 改密码时用：删掉这个人除当前这条以外的会话。
func (s *Store) DeleteOthers(ctx context.Context, userID int64, keepCookie string) error {
	return s.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		return s.DeleteOthersTx(ctx, tx, userID, keepCookie)
	})
}

// DeleteAllTx 在已有写事务里删掉这个人的全部会话。
func (s *Store) DeleteAllTx(ctx context.Context, tx *db.Tx, userID int64) error {
	_, err := tx.ExecContext(ctx, `DELETE FROM sessions WHERE user_id = ?`, userID)
	return err
}

// DeleteAll 停用、注销时删掉这个人的全部会话。
func (s *Store) DeleteAll(ctx context.Context, userID int64) error {
	return s.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		return s.DeleteAllTx(ctx, tx, userID)
	})
}

// MarkReauth 记下「刚刚输过密码」。
func (s *Store) MarkReauth(ctx context.Context, cookie string) error {
	raw, err := decodeToken(cookie)
	if err != nil {
		return nil
	}
	now := db.FormatUTC(s.clock.Now().UTC())
	return s.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, `UPDATE sessions SET reauth_at = ? WHERE token_hash = ?`, now, hashToken(raw))
		return err
	})
}

// SetNoticeTx 用已有事务保存提示；不能给别人的会话写提示。
func (s *Store) SetNoticeTx(ctx context.Context, tx *db.Tx, userID int64, cookie, notice string) error {
	raw, err := decodeToken(cookie)
	if err != nil {
		return nil
	}
	_, err = tx.ExecContext(ctx, `UPDATE sessions SET flash_message = ? WHERE token_hash = ? AND user_id = ?`, notice, hashToken(raw), userID)
	return err
}

// PopNotice 原子消费；同时请求只有一个拿到。空提示的普通读取不占写车道。
func (s *Store) PopNotice(ctx context.Context, cookie string) (string, error) {
	raw, err := decodeToken(cookie)
	if err != nil {
		return "", nil
	}
	key, now := hashToken(raw), db.FormatUTC(s.clock.Now())
	var notice string
	err = s.db.ReadPool().QueryRowContext(ctx, `SELECT flash_message FROM sessions WHERE token_hash = ? AND expires_at > ?`, key, now).Scan(&notice)
	if errors.Is(err, sql.ErrNoRows) {
		return "", nil
	}
	if err != nil || notice == "" {
		return notice, err
	}
	err = s.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		err := tx.QueryRowContext(ctx, `SELECT flash_message FROM sessions WHERE token_hash = ? AND expires_at > ?`, key, now).Scan(&notice)
		if errors.Is(err, sql.ErrNoRows) {
			notice = ""
			return nil
		}
		if err != nil || notice == "" {
			return err
		}
		_, err = tx.ExecContext(ctx, `UPDATE sessions SET flash_message = '' WHERE token_hash = ?`, key)
		return err
	})
	return notice, err
}

// Touch 更新最后访问时间；距上次不到一小时就什么都不写。
func (s *Store) Touch(ctx context.Context, cookie string) error {
	sess, err := s.Lookup(ctx, cookie)
	if err != nil || sess == nil {
		return err
	}
	now := s.clock.Now()
	if now.Sub(sess.LastSeen) < TouchEvery {
		return nil
	}
	raw, err := decodeToken(cookie)
	if err != nil {
		return nil
	}
	return s.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, `UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?`,
			db.FormatUTC(now), hashToken(raw))
		return err
	})
}

func scanSession(userID int64, created, expires, reauth, seen string) (*Session, error) {
	c, err := db.ParseUTC(created)
	if err != nil {
		return nil, err
	}
	e, err := db.ParseUTC(expires)
	if err != nil {
		return nil, err
	}
	seenAt, err := db.ParseUTC(seen)
	if err != nil {
		return nil, err
	}
	sess := &Session{UserID: userID, CreatedAt: c, ExpiresAt: e, LastSeen: seenAt}
	if reauth != "" {
		r, err := db.ParseUTC(reauth)
		if err != nil {
			return nil, err
		}
		sess.ReauthAt = r
	}
	return sess, nil
}

func decodeToken(cookie string) ([]byte, error) {
	raw, err := base64.RawURLEncoding.DecodeString(cookie)
	if err != nil || len(raw) != 32 {
		return nil, errors.New("坏的会话令牌")
	}
	return raw, nil
}

func hashToken(raw []byte) string {
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}
