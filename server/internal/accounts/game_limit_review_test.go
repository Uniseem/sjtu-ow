package accounts

import (
	"context"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"testing"
)

func TestConfiguredGameAccountLimitIsEnforcedAndProjected(t *testing.T) {
	d := newTestDB(t)
	user := newVerifiedUser(t, d, "limit@example.test", "上限", "Password123!@#", true)
	if _, err := d.WritePool().Exec(`UPDATE site_settings SET max_game_accounts=1 WHERE id=1`); err != nil {
		t.Fatal(err)
	}
	svc := NewService(d, clock.System{}, "https://example.test", nil, nil)
	ctx := newTestCtx(context.Background(), user, "", false)
	if _, err := svc.AddGameAccount(ctx, AddGameAccountInput{Battletag: "First#1234"}); err != nil {
		t.Fatal(err)
	}
	if _, err := svc.AddGameAccount(ctx, AddGameAccountInput{Battletag: "Second#1234"}); err == nil {
		t.Fatal("configured per-user limit ignored")
	}
	current, err := svc.personalContext(ctx, user)
	if err != nil {
		t.Fatal(err)
	}
	if current.MaxGameAccounts != 1 {
		t.Fatalf("personal form limit=%d", current.MaxGameAccounts)
	}
}
