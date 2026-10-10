package accounts

import (
	"context"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type EmailState struct {
	Email           string `json:"email"`
	PendingEmail    string `json:"pending_email,omitempty"`
	Reauthenticated bool   `json:"reauthenticated"`
}

func (s *Service) EmailChangeState(ctx *app.Ctx) (*EmailState, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled {
		return nil, api.Unauthorized("要先登录")
	}
	u, err := s.store.GetByID(ctx.Context, ctx.Viewer.ID)
	if err != nil {
		return nil, err
	}
	if u == nil || !u.IsActive {
		return nil, api.Unauthorized("账号不存在或已停用")
	}
	out := &EmailState{Email: u.Email}
	sess, err := s.sessions.Lookup(ctx.Context, ctx.SessionToken)
	if err != nil {
		return nil, err
	}
	out.Reauthenticated = sess != nil && sess.UserID == u.ID && sess.RecentlyReauthed(s.clock.Now())
	ec, err := scanEmailChange(s.d.ReadPool().QueryRowContext(ctx.Context, `SELECT user_id, new_email, new_email_norm, code_hash, attempts, created_at, expires_at FROM email_changes WHERE user_id = ?`, u.ID))
	if err != nil {
		return nil, err
	}
	if ec != nil && s.clock.Now().Before(ec.ExpiresAt) && ec.Attempts < 3 {
		out.PendingEmail = ec.NewEmail
	}
	return out, nil
}

func (s *Service) CancelEmailChange(ctx *app.Ctx) (*ConfirmEmailChangeResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled {
		return nil, api.Unauthorized("要先登录")
	}
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		return s.store.DeleteEmailChange(txCtx, tx, ctx.Viewer.ID)
	})
	if err != nil {
		return nil, err
	}
	return &ConfirmEmailChangeResult{Result: "ok", Message: "已取消修改邮箱。"}, nil
}

// Return a validation error only after committing attempt counters/deletion.
func (s *Service) confirmEmailChange(ctx *app.Ctx, in ConfirmEmailChangeInput) (*ConfirmEmailChangeResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	code := strings.TrimSpace(in.Code)
	if len(code) != 6 {
		return nil, api.InvalidFields(map[string][]string{"code": {"请输入 6 位数字验证码。"}})
	}
	now := s.clock.Now().UTC()
	var validation error
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		ec, err := s.store.GetEmailChangeTx(txCtx, tx, ctx.Viewer.ID)
		if err != nil {
			return err
		}
		if ec == nil || !now.Before(ec.ExpiresAt) || ec.Attempts >= 3 {
			validation = api.InvalidFields(map[string][]string{"code": {"验证码已失效，请重新申请。"}})
			return s.store.DeleteEmailChange(txCtx, tx, ctx.Viewer.ID)
		}
		sum := sha256.Sum256([]byte(code))
		if subtle.ConstantTimeCompare([]byte(hex.EncodeToString(sum[:])), []byte(ec.CodeHash)) != 1 {
			validation = api.InvalidFields(map[string][]string{"code": {"验证码不正确。"}})
			if ec.Attempts+1 >= 3 {
				return s.store.DeleteEmailChange(txCtx, tx, ctx.Viewer.ID)
			}
			return s.store.BumpEmailChangeAttempts(txCtx, tx, ctx.Viewer.ID)
		}
		u, err := s.store.GetByIDTx(txCtx, tx, ctx.Viewer.ID)
		if err != nil {
			return err
		}
		if u == nil || !u.IsActive {
			return api.Unauthorized("账号不存在或已停用")
		}
		existing, err := s.store.GetByEmailNormTx(txCtx, tx, ec.NewEmailNorm)
		if err != nil {
			return err
		}
		if existing != nil && existing.ID != u.ID {
			return api.InvalidFields(map[string][]string{"code": {"该邮箱已被占用。"}})
		}
		if err := s.store.UpdateUserEmail(txCtx, tx, u.ID, ec.NewEmail, ec.NewEmailNorm, now); err != nil {
			return err
		}
		// Reset credentials bound to the previous address must not survive a change.
		if err := s.store.DeleteEmailCodes(txCtx, tx, "password_reset", u.EmailNorm); err != nil {
			return err
		}
		if err := s.store.DeleteEmailCodes(txCtx, tx, resetGrantPurpose, u.EmailNorm); err != nil {
			return err
		}
		if err := s.sessions.SetNoticeTx(txCtx, tx, u.ID, ctx.SessionToken, "邮箱修改成功。"); err != nil {
			return err
		}
		return s.store.DeleteEmailChange(txCtx, tx, u.ID)
	})
	if err != nil {
		return nil, err
	}
	if validation != nil {
		return nil, validation
	}
	return &ConfirmEmailChangeResult{Result: "ok", Message: "邮箱修改成功。"}, nil
}
