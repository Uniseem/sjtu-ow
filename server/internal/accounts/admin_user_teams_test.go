package accounts

import (
	"context"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"testing"
	"time"
)

func TestAdminUserDetailIncludesMembershipRoles(t *testing.T) {
	d := newTestDB(t)
	user := newVerifiedUser(t, d, "member@example.test", "成员", "Password123!@#", true)
	at := db.FormatUTC(time.Now().UTC())
	_, err := d.WritePool().Exec(`INSERT INTO teams(id,name,created_at,updated_at) VALUES(100,'成员的战队',?,?)`, at, at)
	if err != nil {
		t.Fatal(err)
	}
	_, err = d.WritePool().Exec(`INSERT INTO team_memberships(team_id,user_id,role,joined_at) VALUES(100,?,'captain',?)`, user.ID, at)
	if err != nil {
		t.Fatal(err)
	}
	svc := NewService(d, clock.System{}, "https://example.test", nil, nil)
	result, err := svc.GetUserDetail(newTestCtx(context.Background(), nil, "", true), UserDetailInput{ID: api.ID(user.ID)})
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Teams) != 1 || result.Teams[0].Name != "成员的战队" || result.Teams[0].Role != "captain" {
		t.Fatalf("membership missing: %+v", result.Teams)
	}
}
