package accounts

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/base64"
	"errors"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type CodeFlowState struct {
	Active bool   `json:"active"`
	Email  string `json:"email,omitempty"`
}

func (s *Service) startCodeFlow(ctx *app.Ctx, purpose, email string) error {
	bytes := make([]byte, 32)
	if _, err := rand.Read(bytes); err != nil {
		return err
	}
	token := base64.RawURLEncoding.EncodeToString(bytes)
	lifetime := 15 * time.Minute
	if purpose == "password_reset" {
		lifetime = 3 * time.Minute
	}
	now := s.clock.Now().UTC()
	expires := now.Add(lifetime)
	err := s.d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		oldHash := resetTokenHash(ctx.CodeFlowTokens[purpose])
		if oldHash != "" {
			if _, err := tx.ExecContext(c, "DELETE FROM account_code_flows WHERE token_hash=? AND purpose=?", oldHash, purpose); err != nil {
				return err
			}
		}
		_, err := tx.ExecContext(c, `INSERT INTO account_code_flows(token_hash,purpose,email_norm,created_at,expires_at) VALUES(?,?,?,?,?)`, resetTokenHash(token), purpose, NormalizeEmail(email), db.FormatUTC(now), db.FormatUTC(expires))
		return err
	})
	if err != nil {
		return err
	}
	ctx.SetCodeFlowCookie(purpose, token, expires)
	return nil
}
func (s *Service) codeFlowState(ctx context.Context, purpose, token string) (CodeFlowState, error) {
	state := CodeFlowState{}
	hash := resetTokenHash(token)
	if hash == "" {
		return state, nil
	}
	err := s.d.ReadPool().QueryRowContext(ctx, `SELECT email_norm FROM account_code_flows WHERE token_hash=? AND purpose=? AND closed=0 AND attempts<3 AND expires_at>?`, hash, purpose, db.FormatUTC(s.clock.Now())).Scan(&state.Email)
	if errors.Is(err, sql.ErrNoRows) {
		return CodeFlowState{}, nil
	}
	if err != nil {
		return state, err
	}
	state.Active = true
	return state, nil
}

// Called in the actual verification transaction. A supplied cookie cannot be
// used for another address/purpose; missing cookies retain direct API behavior.
func reserveCodeFlow(ctx context.Context, tx *db.Tx, purpose, email, token string, now time.Time) (bool, error) {
	if token == "" {
		return true, nil
	}
	hash := resetTokenHash(token)
	if hash == "" {
		return false, nil
	}
	result, err := tx.ExecContext(ctx, `UPDATE account_code_flows SET attempts=attempts+1,closed=CASE WHEN attempts+1>=3 THEN 1 ELSE 0 END
  WHERE token_hash=? AND purpose=? AND email_norm=? AND closed=0 AND attempts<3 AND expires_at>?`, hash, purpose, email, db.FormatUTC(now))
	if err != nil {
		return false, err
	}
	count, err := result.RowsAffected()
	return count == 1, err
}
func closeCodeFlow(ctx context.Context, tx *db.Tx, purpose, token string) error {
	if token == "" {
		return nil
	}
	_, err := tx.ExecContext(ctx, "UPDATE account_code_flows SET closed=1 WHERE token_hash=? AND purpose=?", resetTokenHash(token), purpose)
	return err
}
func (s *Service) CleanupCodeFlows(ctx context.Context, now time.Time) (int64, error) {
	var count int64
	err := s.d.WriteTx(ctx, func(c context.Context, tx *db.Tx) error {
		result, err := tx.ExecContext(c, "DELETE FROM account_code_flows WHERE expires_at<=?", db.FormatUTC(now))
		if err != nil {
			return err
		}
		count, err = result.RowsAffected()
		return err
	})
	return count, err
}

// RevokeCodeFlowsForEmail erases anonymous workflow PII when an account is
// anonymized; the lifecycle caller already owns the single writer transaction.
func RevokeCodeFlowsForEmail(ctx context.Context, tx *db.Tx, email string) error {
	_, err := tx.ExecContext(ctx, "DELETE FROM account_code_flows WHERE email_norm=?", NormalizeEmail(email))
	return err
}
