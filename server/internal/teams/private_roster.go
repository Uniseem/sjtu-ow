package teams

import (
	"context"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// PrivateGameAccount is visible to the team's manager because an applicant
// explicitly agreed to this disclosure. It is never embedded in Person.
type PrivateGameAccount struct {
	ID          int64  `json:"id"`
	Battletag   string `json:"battletag"`
	RankSummary string `json:"rank_summary"`
}

func privateGameAccount(account accounts.GameAccount) PrivateGameAccount {
	ranks := []string{}
	for _, role := range []struct {
		label string
		score *int
	}{{"坦克", account.RankTank}, {"输出", account.RankDamage}, {"支援", account.RankSupport}} {
		if role.score != nil {
			ranks = append(ranks, role.label+" "+accounts.FormatRank(role.score))
		}
	}
	summary := strings.Join(ranks, "、")
	if summary == "" {
		summary = "未填写段位"
	}
	return PrivateGameAccount{ID: account.ID, Battletag: account.Battletag, RankSummary: summary}
}
func (s *Service) fillPrivateRoster(ctx context.Context, q db.DBTX, members []MemberRow) error {
	ids := make([]int64, 0, len(members))
	for _, member := range members {
		ids = append(ids, member.UserID)
	}
	games, err := s.store.GameAccountsFor(ctx, q, ids)
	if err != nil {
		return err
	}
	for index := range members {
		members[index].GameIDs = []string{}
		members[index].GameAccounts = []PrivateGameAccount{}
		for _, game := range games[members[index].UserID] {
			members[index].GameIDs = append(members[index].GameIDs, game.Battletag)
			members[index].GameAccounts = append(members[index].GameAccounts, privateGameAccount(game))
		}
	}
	return nil
}
