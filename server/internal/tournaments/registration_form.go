package tournaments

import (
	"context"
	"database/sql"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// GameAccountChoice is disclosed only to the account owner or a current
// captain choosing the game IDs for the current members of their own team.
type GameAccountChoice struct {
	ID          int64  `json:"id"`
	Battletag   string `json:"battletag"`
	RankTank    *int   `json:"rank_tank"`
	RankDamage  *int   `json:"rank_damage"`
	RankSupport *int   `json:"rank_support"`
}

type RegisterTeamChoice struct {
	ID      int64  `json:"id"`
	Name    string `json:"name"`
	Version int64  `json:"version"`
}

type RegisterMember struct {
	UserID            int64               `json:"user_id"`
	Nickname          string              `json:"nickname"`
	IsCaptain         bool                `json:"is_captain"`
	IsSJTU            bool                `json:"is_sjtu"`
	Accounts          []GameAccountChoice `json:"accounts"`
	SelectedAccountID *int64              `json:"selected_account_id"`
	Problems          []string            `json:"problems"`
}

type RegisterForm struct {
	Tournament *Tournament          `json:"tournament"`
	Teams      []RegisterTeamChoice `json:"teams"`
	Team       *RegisterTeamChoice  `json:"team"`
	Rows       []RegisterMember     `json:"rows"`
	Existing   *Registration        `json:"existing"`
	Problems   []string             `json:"problems"`
	CanSubmit  bool                 `json:"can_submit"`
}

type RegisterFormIn struct {
	ID   api.ID `path:"id"`
	Team int64  `query:"team"`
}

type IndividualForm struct {
	Tournament           *Tournament         `json:"tournament"`
	GameAccounts         []GameAccountChoice `json:"game_accounts"`
	MySignup             *SignupView         `json:"my_signup"`
	RegistrationTeamName string              `json:"registration_team_name"`
	Problems             []string            `json:"problems"`
	CanSubmit            bool                `json:"can_submit"`
	CanCancel            bool                `json:"can_cancel"`
}

func accountChoices(ctx context.Context, q db.DBTX, userID int64) ([]GameAccountChoice, error) {
	rows, err := q.QueryContext(ctx, `SELECT id,battletag,rank_tank,rank_damage,rank_support
		FROM game_accounts WHERE user_id = ? ORDER BY id`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []GameAccountChoice{}
	for rows.Next() {
		var choice GameAccountChoice
		var tank, damage, support sql.NullInt64
		if err := rows.Scan(&choice.ID, &choice.Battletag, &tank, &damage, &support); err != nil {
			return nil, err
		}
		for _, pair := range []struct {
			value  sql.NullInt64
			target **int
		}{
			{tank, &choice.RankTank}, {damage, &choice.RankDamage}, {support, &choice.RankSupport},
		} {
			if pair.value.Valid {
				value := int(pair.value.Int64)
				*pair.target = &value
			}
		}
		out = append(out, choice)
	}
	return out, rows.Err()
}

func captainChoices(ctx context.Context, q db.DBTX, actor int64) ([]RegisterTeamChoice, error) {
	rows, err := q.QueryContext(ctx, `SELECT t.id,t.name,t.version FROM teams t
		JOIN team_memberships member ON member.team_id=t.id
		WHERE member.user_id=? AND member.role='captain' AND t.disbanded_at IS NULL
		ORDER BY member.joined_at,member.id`, actor)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []RegisterTeamChoice{}
	for rows.Next() {
		var choice RegisterTeamChoice
		if err := rows.Scan(&choice.ID, &choice.Name, &choice.Version); err != nil {
			return nil, err
		}
		out = append(out, choice)
	}
	return out, rows.Err()
}

// RegisterForm exposes one selected team's current roster only after proving
// captainship. A query parameter pointing to another team never discloses it;
// it falls back to the same first captained team as the legacy page.
func (s *Service) RegisterForm(ctx *app.Ctx, id, selectedTeam int64) (*RegisterForm, error) {
	viewer, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	q, err := s.d.ReadPool().BeginTx(ctx.Context, &sql.TxOptions{ReadOnly: true})
	if err != nil {
		return nil, err
	}
	defer q.Rollback()
	snapshotCtx := *ctx
	snapshotCtx.Context = cachedProjectionContext(ctx.Context)
	ctx = &snapshotCtx
	item, err := GetTournament(ctx.Context, q, id)
	if err != nil {
		return nil, err
	}
	if item == nil || !item.IsPublic() {
		return nil, api.NotFound("赛事不存在")
	}
	choices, err := captainChoices(ctx.Context, q, viewer.ID)
	if err != nil {
		return nil, err
	}
	out := &RegisterForm{Tournament: item, Teams: choices, Rows: []RegisterMember{}, Problems: []string{}}
	if len(choices) == 0 {
		item.ParticipantContact = ""
		out.Problems = append(out.Problems, "需要由队长为战队报名。")
		return out, nil
	}
	selected := choices[0]
	for _, choice := range choices {
		if choice.ID == selectedTeam {
			selected = choice
			break
		}
	}
	out.Team = &selected
	existing, err := registrationForTeam(ctx.Context, q, id, selected.ID)
	if err != nil {
		return nil, err
	}
	out.Existing = existing
	var excluded int64
	if existing != nil {
		excluded = existing.ID
	}
	out.Problems, err = s.precheck(ctx.Context, q, item, selected.ID, viewer.ID, excluded, ctx.Now().UTC())
	if err != nil {
		return nil, err
	}
	if out.Problems == nil {
		out.Problems = []string{}
	}
	members, err := teamMembers(ctx.Context, q, selected.ID)
	if err != nil {
		return nil, err
	}
	memberAccounts, err := memberAccountChoices(ctx.Context, q, members)
	if err != nil {
		return nil, err
	}
	for _, member := range members {
		accounts := memberAccounts[member.UserID]
		memberProblems, err := s.memberProblems(ctx.Context, q, item, member.UserID, false)
		if err != nil {
			return nil, err
		}
		conflict, err := s.rosterConflict(ctx.Context, q, item.ID, member.UserID, excluded)
		if err != nil {
			return nil, err
		}
		if conflict != "" {
			memberProblems = append(memberProblems, conflict)
		}
		if memberProblems == nil {
			memberProblems = []string{}
		}
		row := RegisterMember{UserID: member.UserID, Nickname: member.Nickname,
			IsCaptain: member.IsCaptain, IsSJTU: member.IsSJTU, Accounts: accounts, Problems: memberProblems}
		if len(accounts) > 0 {
			first := accounts[0].ID
			row.SelectedAccountID = &first
		}
		out.Rows = append(out.Rows, row)
	}
	out.CanSubmit = len(out.Problems) == 0
	participating, err := s.takesPart(ctx.Context, q, id, viewer.ID)
	if err != nil {
		return nil, err
	}
	if !participating && (existing == nil || !existing.Active()) {
		item.ParticipantContact = ""
	}
	return out, nil
}

func registrationForTeam(ctx context.Context, q db.DBTX, tournament, team int64) (*Registration, error) {
	row := q.QueryRowContext(ctx, `SELECT `+regCols+` FROM registrations WHERE tournament_id=? AND team_id=?`, tournament, team)
	registration, err := scanRegistration(row)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return registration, err
}

func (s *Service) IndividualForm(ctx *app.Ctx, id int64) (*IndividualForm, error) {
	viewer, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	q, err := s.d.ReadPool().BeginTx(ctx.Context, &sql.TxOptions{ReadOnly: true})
	if err != nil {
		return nil, err
	}
	defer q.Rollback()
	item, err := GetTournament(ctx.Context, q, id)
	if err != nil {
		return nil, err
	}
	if item == nil || !item.IsPublic() {
		return nil, api.NotFound("赛事不存在")
	}
	accounts, err := accountChoices(ctx.Context, q, viewer.ID)
	if err != nil {
		return nil, err
	}
	signup, err := getSignup(ctx.Context, q, id, viewer.ID)
	if err != nil {
		return nil, err
	}
	out := &IndividualForm{Tournament: item, GameAccounts: accounts, Problems: []string{}}
	if signup != nil {
		out.MySignup = viewOf(signup)
		if signup.RegistrationID != nil {
			registration, err := GetRegistration(ctx.Context, q, *signup.RegistrationID)
			if err != nil {
				return nil, err
			}
			if registration != nil {
				out.RegistrationTeamName = registration.TeamName
			}
		}
	}
	out.Problems, err = s.individualProblems(ctx.Context, q, item, viewer.ID, ctx.Now().UTC())
	if err != nil {
		return nil, err
	}
	if out.Problems == nil {
		out.Problems = []string{}
	}
	out.CanSubmit = len(out.Problems) == 0 && (signup == nil || !signup.Placed()) && len(accounts) > 0
	out.CanCancel = signup != nil && !signup.Placed() && item.RegistrationOpen(ctx.Now().UTC())
	participating, err := s.takesPart(ctx.Context, q, id, viewer.ID)
	if err != nil {
		return nil, err
	}
	if !participating {
		item.ParticipantContact = ""
	}
	return out, nil
}

func (m *Module) registerForm(ctx *app.Ctx, in RegisterFormIn) (*RegisterForm, error) {
	return m.svc.RegisterForm(ctx, int64(in.ID), in.Team)
}

func (m *Module) individualForm(ctx *app.Ctx, in IDIn) (*IndividualForm, error) {
	return m.svc.IndividualForm(ctx, int64(in.ID))
}
