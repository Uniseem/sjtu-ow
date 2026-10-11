package tournaments

import (
	"testing"
)

func TestRegisterFormDoesNotDiscloseAnotherCaptainsGameIDs(t *testing.T) {
	e := newEnv(t)
	id := e.tour()
	captain, member, other := e.user("队长"), e.user("队员"), e.user("另一队长")
	own := e.team("自己的队", captain, member)
	foreign := e.team("别人的队", other)
	form, err := e.svc.RegisterForm(e.ctx(captain), id, foreign)
	if err != nil {
		t.Fatal(err)
	}
	if form.Team == nil || form.Team.ID != own || len(form.Rows) != 2 {
		t.Fatalf("foreign selector did not use own team: %+v", form)
	}
	for _, row := range form.Rows {
		if row.UserID == other {
			t.Fatal("foreign roster disclosed")
		}
		for _, account := range row.Accounts {
			if account.ID == e.firstAccount(other) {
				t.Fatal("foreign game ID disclosed")
			}
		}
	}
	outsider, err := e.svc.RegisterForm(e.ctx(member), id, own)
	if err != nil {
		t.Fatal(err)
	}
	if outsider.Team != nil || len(outsider.Rows) != 0 || outsider.CanSubmit {
		t.Fatalf("ordinary member read captain's form: %+v", outsider)
	}
}

func TestRegistrationSubmitRejectsChangedTeamSnapshot(t *testing.T) {
	e := newEnv(t)
	id := e.tour()
	captain, member := e.user("队长"), e.user("队员")
	team := e.team("战队", captain, member)
	form, err := e.svc.RegisterForm(e.ctx(captain), id, team)
	if err != nil {
		t.Fatal(err)
	}
	e.exec(`UPDATE teams SET version=version+1 WHERE id=?`, team)
	_, err = e.svc.Submit(e.ctx(captain), SubmitInput{TournamentID: id, TeamID: team, BaseTeamVersion: form.Team.Version})
	if err == nil {
		t.Fatal("changed team version accepted")
	}
	if e.count(`SELECT COUNT(*) FROM registrations WHERE tournament_id=?`, id) != 0 {
		t.Fatal("rejected snapshot wrote registration")
	}
}

func TestPersonalRegistrationProjectionContainsOnlyActorSignups(t *testing.T) {
	e := newEnv(t)
	id := e.tour(withMode(ModeIndividual))
	one, two := e.user("甲"), e.user("乙")
	for _, user := range []int64{one, two} {
		if _, err := e.svc.SignUpIndividual(e.ctx(user), SignupInput{TournamentID: id, GameAccountID: e.firstAccount(user), Roles: []string{"tank"}}); err != nil {
			t.Fatal(err)
		}
	}
	mine, err := e.svc.PersonalRegistrations(e.ctx(one))
	if err != nil {
		t.Fatal(err)
	}
	if len(mine.IndividualSignups) != 1 {
		t.Fatalf("private signup count=%d", len(mine.IndividualSignups))
	}
	if mine.IndividualSignups[0].GameAccountID == nil || *mine.IndividualSignups[0].GameAccountID != e.firstAccount(one) {
		t.Fatal("private signup used another person's game account")
	}
	if mine.IndividualSignups[0].Battletag == nil || !mine.IndividualSignups[0].CanCancel {
		t.Fatal("own active signup projection incomplete")
	}
}
