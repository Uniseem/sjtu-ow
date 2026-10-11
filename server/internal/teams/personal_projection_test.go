package teams

import "testing"

func TestMyTeamsProjectsOnlyOwnActiveContactsAndRetirement(t *testing.T) {
	e := newEnv(t)
	owner, other := e.user("本人"), e.user("他人")
	first, second := e.team(owner, "当前战队"), e.team(other, "他人战队")
	e.exec(`UPDATE teams SET member_contact='private-own-contact' WHERE id=?`, first.ID)
	e.exec(`UPDATE teams SET member_contact='private-other-contact' WHERE id=?`, second.ID)
	e.exec(`INSERT INTO team_alumni(team_id,user_id,role,joined_at,left_at,reason) VALUES(?,?,'member','2026-09-01T00:00:00Z','2026-10-01T00:00:00Z','left')`, second.ID, owner)
	e.exec(`INSERT INTO team_alumni(team_id,user_id,role,joined_at,left_at,reason) VALUES(?,?,'member','2026-09-01T00:00:00Z','2026-10-01T00:00:00Z','removed')`, first.ID, other)
	mine, err := e.svc.MyTeams(e.ctx(owner, false))
	if err != nil {
		t.Fatal(err)
	}
	if len(mine.Teams) != 1 || mine.Teams[0].TeamID != first.ID || mine.Teams[0].MemberContact != "private-own-contact" {
		t.Fatalf("wrong private memberships: %+v", mine.Teams)
	}
	if len(mine.Alumni) != 1 || mine.Alumni[0].TeamID != second.ID || mine.Alumni[0].TeamName != "他人战队" {
		t.Fatalf("wrong own retirement: %+v", mine.Alumni)
	}
	e.exec(`UPDATE teams SET disbanded_at='2026-10-02T00:00:00Z' WHERE id=?`, second.ID)
	mine, err = e.svc.MyTeams(e.ctx(owner, false))
	if err != nil || len(mine.Alumni) != 0 {
		t.Fatalf("disbanded retirement remains: %+v %v", mine, err)
	}
	if _, err := e.svc.MyTeams(e.anon()); err == nil {
		t.Fatal("visitor read private memberships")
	}
	public, err := e.svc.List(e.anon().Context, ListInput{})
	if err != nil || len(public.Teams) != 1 || public.Teams[0].CreatedAt.IsZero() {
		t.Fatalf("public creation date missing: %+v %v", public, err)
	}
}
