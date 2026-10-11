package scrims

import (
	"errors"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

func TestOpenQueueCannotCreateSignupWithUnknownOnlyRole(t *testing.T) {
	e := newEnv(t)
	id := e.scrim(withFormat(Open5))
	user := e.user("成员", 10, 0, 0)
	_, err := e.svc.SignUp(e.ctx(user), SignupInput{ScrimID: id, GameAccountID: e.account(user), Roles: []string{"made-up"}})
	if err == nil {
		t.Fatal("unknown-only position was accepted")
	}
	if e.count(`SELECT COUNT(*) FROM scrim_signups WHERE scrim_id=?`, id) != 0 {
		t.Fatal("invalid signup persisted")
	}
}

func TestUnplacedSignupChangesInvalidateOpenBoard(t *testing.T) {
	e := newEnv(t)
	id := e.scrim(withFormat(Open5))
	user := e.user("成员", 10, 0, 0)
	old, err := e.svc.GetBoard(e.mgr(), id, "")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := e.svc.SignUp(e.ctx(user), SignupInput{ScrimID: id, GameAccountID: e.account(user), Roles: []string{Tank}}); err != nil {
		t.Fatal(err)
	}
	_, err = e.svc.SetSelection(e.mgr(), id, nil, old.BoardVersion)
	var stale *api.Error
	if !errors.As(err, &stale) || stale.Status != 409 {
		t.Fatalf("new signup did not invalidate board: %v", err)
	}
	current, err := e.svc.GetBoard(e.mgr(), id, "")
	if err != nil {
		t.Fatal(err)
	}
	if current.TeamsStale {
		t.Fatal("never-split roster was falsely marked as an obsolete split")
	}
	if err := e.svc.CancelSignup(e.ctx(user), id); err != nil {
		t.Fatal(err)
	}
	if _, err := e.svc.SetSelection(e.mgr(), id, nil, current.BoardVersion); err == nil {
		t.Fatal("cancelled unplaced signup did not invalidate board")
	}
}

func TestScrimPublicProjectionDoesNotExposePrivatePlacement(t *testing.T) {
	e := newEnv(t)
	id := e.scrim(withFormat(Open5))
	one, two := e.user("甲", 10, 0, 0), e.user("乙", 0, 20, 0)
	for _, user := range []int64{one, two} {
		if _, err := e.svc.SignUp(e.ctx(user), SignupInput{ScrimID: id, GameAccountID: e.account(user), Roles: []string{Tank}}); err != nil {
			t.Fatal(err)
		}
	}
	public, err := e.svc.Detail(e.anon(), id)
	if err != nil {
		t.Fatal(err)
	}
	if public.Mine != nil || len(public.GameAccounts) != 0 || public.GroupURL != "" {
		t.Fatalf("public detail disclosed private context: %+v", public)
	}
	mine, err := e.svc.Personal(e.ctx(one))
	if err != nil {
		t.Fatal(err)
	}
	if len(mine.Signups) != 1 || mine.Signups[0].GameAccountID == nil || *mine.Signups[0].GameAccountID != e.account(one) {
		t.Fatal("personal history includes foreign game IDs")
	}
	form, err := e.svc.SignupForm(e.ctx(one), id)
	if err != nil {
		t.Fatal(err)
	}
	if len(form.GameAccounts) != 1 || form.GameAccounts[0].ID != e.account(one) {
		t.Fatal("private form disclosed foreign game accounts")
	}
}
