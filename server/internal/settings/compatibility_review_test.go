package settings

import (
	"context"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"testing"
)

func TestLegacyCommunitySettingsPatchAndReadback(t *testing.T) {
	d := newTestDB(t)
	svc := NewService(d, "https://example.test", "01234567890123456789012345678901")
	ctx := &app.Ctx{Context: context.Background(), Viewer: &app.Viewer{ID: 1, Superuser: true}}
	initial, err := svc.Get(ctx.Context)
	if err != nil {
		t.Fatal(err)
	}
	games, images := 2, true
	receipt, err := svc.patchFields(ctx, &initial.Version, SettingsChanges{MaxGameAccounts: &games, ModerationImageEnabled: &images})
	if err != nil {
		t.Fatal(err)
	}
	if receipt.Settings.MaxGameAccounts != games || !receipt.Settings.ModerationImageEnabled {
		t.Fatal("legacy settings omitted from receipt")
	}
	negative := -1
	invalid, err := svc.patchFields(ctx, &receipt.Version, SettingsChanges{MaxGameAccounts: &negative})
	if err != nil {
		t.Fatal(err)
	}
	if len(invalid.Fields["max_game_accounts"]) == 0 {
		t.Fatal("negative game account cap accepted")
	}
	current, err := svc.Get(ctx.Context)
	if err != nil {
		t.Fatal(err)
	}
	if current.MaxGameAccounts != 2 {
		t.Fatal("invalid value overwrote configured limit")
	}
}
