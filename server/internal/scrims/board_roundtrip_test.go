package scrims

import (
	"net/http"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
)

// Browser sends every signup, including explicit empty-team buffer entries.
// Verify the persisted read, then use its version to move the player back.
func TestBoardBufferRoundTripPreservesSelection(t *testing.T) {
	e := newEnv(t)
	sid := e.scrim()
	users := e.tenPlayers(sid, FormatRQ5)
	ids := signupIDs(e, sid, users)
	initial, err := e.svc.GetBoard(e.mgr(), sid, "")
	if err != nil {
		t.Fatal(err)
	}
	generated, err := e.svc.Generate(e.mgr(), sid, ids, initial.BoardVersion)
	if err != nil {
		t.Fatal(err)
	}
	var placements []PlacementIn
	for _, signup := range generated.Board.Signups {
		placements = append(placements, PlacementIn{SignupID: signup.SignupID, Team: signup.Team, Role: signup.AssignedRole})
	}
	original := placements[0]
	placements[0].Team, placements[0].Role = "", ""
	if _, err := e.svc.SaveTeams(e.mgr(), sid, placements, generated.Board.BoardVersion); err != nil {
		t.Fatal(err)
	}
	reloaded, err := e.svc.GetBoard(e.mgr(), sid, "")
	if err != nil {
		t.Fatal(err)
	}
	if reloaded.SelectedCount != 10 || len(reloaded.Bench) != 1 || reloaded.Bench[0].SignupID != original.SignupID || !reloaded.Bench[0].IsSelected {
		t.Fatalf("buffer membership or selection lost after reload: %+v", reloaded)
	}
	placements[0] = original
	if _, err := e.svc.SaveTeams(e.mgr(), sid, placements, reloaded.BoardVersion); err != nil {
		t.Fatal(err)
	}
	restored, err := e.svc.GetBoard(e.mgr(), sid, "")
	if err != nil {
		t.Fatal(err)
	}
	if len(restored.Bench) != 0 || restored.SelectedCount != 10 || len(restored.Teams[0].Members) != 5 || len(restored.Teams[1].Members) != 5 {
		t.Fatalf("move back was not persisted: %+v", restored)
	}
}

func TestScrimBoardMutationsRejectOtherManagersBeforeObjectLookup(t *testing.T) {
	e := newEnv(t)
	manager := e.mgr()
	manager.Viewer.Caps = map[app.Cap]struct{}{accounts.CapTournamentsManage: {}, accounts.CapContactsView: {}}
	_, err := e.svc.SetSelection(manager, 999999, []int64{1}, 0)
	wantErr(t, err, http.StatusForbidden, "")
	_, err = e.svc.Generate(manager, 999999, []int64{1}, 0)
	wantErr(t, err, http.StatusForbidden, "")
	_, err = e.svc.SaveTeams(manager, 999999, []PlacementIn{{SignupID: 1, Team: "a", Role: Tank}}, 0)
	wantErr(t, err, http.StatusForbidden, "")
}
