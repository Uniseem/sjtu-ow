package scrims

import (
	"context"
	"database/sql"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type GameAccountChoice struct {
	ID          int64  `json:"id"`
	Battletag   string `json:"battletag"`
	RankTank    *int   `json:"rank_tank"`
	RankDamage  *int   `json:"rank_damage"`
	RankSupport *int   `json:"rank_support"`
}

type SignupForm struct {
	Scrim        *Scrim              `json:"scrim"`
	Card         Card                `json:"card"`
	GameAccounts []GameAccountChoice `json:"game_accounts"`
	Mine         *MySignup           `json:"mine"`
	Problems     []string            `json:"problems"`
	CanSubmit    bool                `json:"can_submit"`
	CanCancel    bool                `json:"can_cancel"`
	RoleQueue    bool                `json:"role_queue"`
	Requirements map[string]int      `json:"requirements"`
}

func accountChoices(ctx context.Context, q db.DBTX, user int64) ([]GameAccountChoice, error) {
	rows, err := q.QueryContext(ctx, `SELECT id,battletag,rank_tank,rank_damage,rank_support FROM game_accounts WHERE user_id=? ORDER BY id`, user)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []GameAccountChoice{}
	for rows.Next() {
		var item GameAccountChoice
		var tank, damage, support sql.NullInt64
		if err := rows.Scan(&item.ID, &item.Battletag, &tank, &damage, &support); err != nil {
			return nil, err
		}
		for _, pair := range []struct {
			value  sql.NullInt64
			target **int
		}{{tank, &item.RankTank}, {damage, &item.RankDamage}, {support, &item.RankSupport}} {
			if pair.value.Valid {
				value := int(pair.value.Int64)
				*pair.target = &value
			}
		}
		out = append(out, item)
	}
	return out, rows.Err()
}

func (s *Service) SignupForm(ctx *app.Ctx, id int64) (*SignupForm, error) {
	viewer, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	q, err := s.d.ReadPool().BeginTx(ctx.Context, &sql.TxOptions{ReadOnly: true})
	if err != nil {
		return nil, err
	}
	defer q.Rollback()
	item, err := GetScrim(ctx.Context, q, id)
	if err != nil {
		return nil, err
	}
	if item == nil || !item.IsPublic() {
		return nil, api.NotFound("内战不存在")
	}
	choices, err := accountChoices(ctx.Context, q, viewer.ID)
	if err != nil {
		return nil, err
	}
	list, err := listSignups(ctx.Context, q, id)
	if err != nil {
		return nil, err
	}
	out := &SignupForm{Scrim: item, Card: cardOf(item, len(list), ctx.Now().UTC()),
		GameAccounts: choices, Problems: []string{}, RoleQueue: item.RoleQueue(), Requirements: map[string]int{}}
	for role, count := range Requirements(item.Format) {
		out.Requirements[role] = count
	}
	var mine *Signup
	hasTeams := false
	for _, signup := range list {
		if signup.UserID == viewer.ID {
			mine = signup
		}
		if signup.Team != "" {
			hasTeams = true
		}
	}
	if mine != nil {
		out.Mine = &MySignup{ID: mine.ID, GameAccountID: mine.GameAccountID, Roles: mine.Roles(),
			Placement: PlacementText(item, mine, hasTeams), CanCancel: item.Deadline() != nil && !ctx.Now().After(*item.Deadline()),
			CanEdit: item.SignupOpen(ctx.Now().UTC())}
		if mine.GameAccountID != nil {
			account, err := getAccount(ctx.Context, q, *mine.GameAccountID)
			if err != nil {
				return nil, err
			}
			if account != nil {
				out.Mine.Battletag = account.Battletag
			} else {
				out.Mine.Battletag = deletedID
			}
		}
		out.CanCancel = out.Mine.CanCancel
	}
	out.Problems, err = s.signupProblems(ctx.Context, q, item, viewer.ID, ctx.Now().UTC())
	if err != nil {
		return nil, err
	}
	if out.Problems == nil {
		out.Problems = []string{}
	}
	out.CanSubmit = len(out.Problems) == 0 && len(choices) > 0
	return out, nil
}

func (m *Module) signupForm(ctx *app.Ctx, in IDIn) (*SignupForm, error) {
	return m.svc.SignupForm(ctx, int64(in.ID))
}
