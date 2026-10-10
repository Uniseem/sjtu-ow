package accounts

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"database/sql"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

const resetGrantPurpose = "password_reset_grant"

type ResetCodeInput struct {
	Email string `json:"email"`
	Code  string `json:"code"`
}

// ResetGrant is internal. Its token may only leave in an HttpOnly cookie.
type ResetGrant struct {
	Token     string
	ExpiresAt time.Time
}

type CompleteResetInput struct {
	Password        string `json:"password"`
	ConfirmPassword string `json:"confirm_password"`
}

type ResetState struct {
	Verified bool   `json:"verified"`
	Email    string `json:"email,omitempty"`
}

func resetTokenHash(token string) string {
	raw, err := base64.RawURLEncoding.DecodeString(token)
	if err != nil || len(raw) != 32 {
		return ""
	}
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}

// VerifyPasswordResetCode consumes the short code, without changing a password.
// Wrong-code mutations must commit; the common error is returned afterwards.
func (s *Service) VerifyPasswordResetCode(ctx context.Context, in ResetCodeInput) (*ResetGrant, error) {
	email, code := NormalizeEmail(in.Email), strings.TrimSpace(in.Code)
	fields := map[string][]string{}
	if !validateEmail(email) {
		fields["email"] = []string{"请输入有效的邮箱地址。"}
	}
	if code == "" {
		fields["code"] = []string{"请输入验证码。"}
	}
	if len(fields) > 0 {
		return nil, api.InvalidFields(fields)
	}
	raw := make([]byte, 32)
	if _, err := rand.Read(raw); err != nil {
		return nil, err
	}
	token := base64.RawURLEncoding.EncodeToString(raw)
	now, passed := s.clock.Now().UTC(), false
	var expiry time.Time
	err := s.d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		u, err := s.store.GetByEmailNormTx(ctx, tx, email)
		if err != nil {
			return err
		}
		if u == nil || !u.IsActive {
			return nil
		}
		c, err := s.store.GetLatestEmailCodeTx(ctx, tx, "password_reset", email)
		if err != nil {
			return err
		}
		if c == nil || !now.Before(c.ExpiresAt) || c.Attempts >= 3 {
			return nil
		}
		sum := sha256.Sum256([]byte(code))
		if subtle.ConstantTimeCompare([]byte(hex.EncodeToString(sum[:])), []byte(c.CodeHash)) != 1 {
			if err := s.store.BumpEmailCodeAttempts(ctx, tx, c.ID); err != nil {
				return err
			}
			if c.Attempts+1 >= 3 {
				return s.store.DeleteEmailCode(ctx, tx, c.ID)
			}
			return nil
		}
		if err := s.store.DeleteEmailCodes(ctx, tx, "password_reset", email); err != nil {
			return err
		}
		if err := s.store.DeleteEmailCodes(ctx, tx, resetGrantPurpose, email); err != nil {
			return err
		}
		if err := s.store.InsertEmailCode(ctx, tx, resetGrantPurpose, email, resetTokenHash(token), now, c.ExpiresAt); err != nil {
			return err
		}
		passed, expiry = true, c.ExpiresAt
		return nil
	})
	if err != nil {
		return nil, err
	}
	if !passed {
		return nil, errBadCode
	}
	return &ResetGrant{Token: token, ExpiresAt: expiry}, nil
}

func (s *Service) PasswordResetState(ctx context.Context, token string) (*ResetState, error) {
	hash := resetTokenHash(token)
	if hash == "" {
		return &ResetState{}, nil
	}
	var email string
	err := s.d.ReadPool().QueryRowContext(ctx, `SELECT u.email FROM email_codes c JOIN users u ON u.email_norm = c.email_norm
		WHERE c.purpose = ? AND c.code_hash = ? AND c.expires_at > ? AND u.is_active = 1`, resetGrantPurpose, hash, db.FormatUTC(s.clock.Now())).Scan(&email)
	if errors.Is(err, sql.ErrNoRows) {
		return &ResetState{}, nil
	}
	if err != nil {
		return nil, err
	}
	return &ResetState{Verified: true, Email: email}, nil
}

// CompletePasswordReset checks the grant again inside the write transaction.
// Hashing a strong password happens outside the SQLite lock.
func (s *Service) CompletePasswordReset(ctx context.Context, token string, in CompleteResetInput) (*ResetPasswordConfirmResult, error) {
	state, err := s.PasswordResetState(ctx, token)
	if err != nil {
		return nil, err
	}
	if !state.Verified {
		return nil, errBadCode
	}
	fields := map[string][]string{}
	if in.Password == "" {
		fields["password"] = []string{"请输入新密码。"}
	} else if pwdErrs := auth.Validate(in.Password, state.Email, ""); len(pwdErrs) > 0 {
		fields["password"] = pwdErrs
	}
	if in.Password != in.ConfirmPassword {
		fields["confirm_password"] = []string{"两次输入的密码不一致。"}
	}
	if len(fields) > 0 {
		return nil, api.InvalidFields(fields)
	}
	passwordHash, err := auth.Hash(ctx, in.Password)
	if err != nil {
		return nil, err
	}
	now, passed := s.clock.Now().UTC(), false
	err = s.d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		u, err := s.store.GetByEmailNormTx(ctx, tx, NormalizeEmail(state.Email))
		if err != nil {
			return err
		}
		if u == nil || !u.IsActive {
			return nil
		}
		grant, err := s.store.GetLatestEmailCodeTx(ctx, tx, resetGrantPurpose, u.EmailNorm)
		if err != nil {
			return err
		}
		if grant == nil || !now.Before(grant.ExpiresAt) || subtle.ConstantTimeCompare([]byte(grant.CodeHash), []byte(resetTokenHash(token))) != 1 {
			return nil
		}
		if _, err := tx.ExecContext(ctx, `UPDATE users SET password_hash = ?, password_changed_at = ?, email_verified_at = COALESCE(email_verified_at, ?), updated_at = ? WHERE id = ?`, passwordHash, db.FormatUTC(now), db.FormatUTC(now), db.FormatUTC(now), u.ID); err != nil {
			return err
		}
		if err := s.store.DeleteEmailCodes(ctx, tx, "password_reset", u.EmailNorm); err != nil {
			return err
		}
		if err := s.store.DeleteEmailCodes(ctx, tx, resetGrantPurpose, u.EmailNorm); err != nil {
			return err
		}
		if err := s.sessions.DeleteAllTx(ctx, tx, u.ID); err != nil {
			return err
		}
		passed = true
		return nil
	})
	if err != nil {
		return nil, err
	}
	if !passed {
		return nil, errBadCode
	}
	return &ResetPasswordConfirmResult{Result: "ok", Message: "密码重置成功，请使用新密码登录。"}, nil
}
