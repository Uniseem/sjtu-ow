package tournaments

import "testing"

func TestPublicActionsContactProjectionRequiresActualParticipation(t *testing.T) {
	e := newEnv(t)
	captain, member := e.user("队长"), e.user("名单队员")
	id := e.tour(withContact("仅供参赛者的群号"))
	reg := e.register(id, e.team("冻结战队名", captain, member), captain)
	manager, err := e.svc.Detail(e.mgr(), id)
	if err != nil {
		t.Fatal(err)
	}
	if manager.Tournament.ParticipantContact != "仅供参赛者的群号" || manager.Viewer.ParticipantContact != "" {
		t.Fatal("manager compatibility field or actual participation projection changed")
	}
	actual, err := e.svc.Detail(e.ctx(member), id)
	if err != nil {
		t.Fatal(err)
	}
	if actual.Viewer.ParticipantContact != "仅供参赛者的群号" || actual.Viewer.OnRoster == nil || actual.Viewer.OnRoster.ID != reg.ID || actual.Viewer.OnRoster.TeamName != "冻结战队名" {
		t.Fatalf("member projection=%+v", actual.Viewer)
	}
	if _, err := e.svc.Reject(e.mgr(), reg.ID, "名单失效"); err != nil {
		t.Fatal(err)
	}
	rejected, err := e.svc.Detail(e.ctx(member), id)
	if err != nil {
		t.Fatal(err)
	}
	if rejected.Viewer.ParticipantContact != "" || rejected.Viewer.OnRoster != nil {
		t.Fatal("inactive roster retained participant-only contact or membership")
	}
}
