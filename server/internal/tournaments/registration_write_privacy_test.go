package tournaments

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

func TestRegistrationWriteRejectsForeignRosterBeforePrivateDiagnostics(t *testing.T) {
	e := newEnv(t)
	tournament := e.tour(withRoster(5, 6))
	captain, member, outsider := e.user("私人队长"), e.user("私人队员"), e.user("外人")
	team := e.team("私人战队", captain, member)
	e.exec(`DELETE FROM contacts WHERE user_id=?`, member)
	e.denied[member] = true
	registry := &api.Registry{}
	NewModule(e.svc).Routes(registry)
	for _, who := range []int64{member, outsider} {
		for _, superuser := range []bool{false, true} {
			viewer := e.ctx(who).Viewer
			viewer.Superuser = superuser
			viewer.Caps = map[app.Cap]struct{}{accounts.CapTournamentsManage: {}}
			handler := registry.Handler(func(*http.Request) *app.Viewer { return viewer })
			for _, teamID := range []int64{team, 999999} {
				request := httptest.NewRequest("POST", fmt.Sprintf("/api/tournaments/%d/registrations", tournament), strings.NewReader(fmt.Sprintf(`{"team_id":%d,"base_team_version":999,"accounts":{}}`, teamID)))
				request.Header.Set("Content-Type", "application/json")
				response := httptest.NewRecorder()
				handler.ServeHTTP(response, request)
				if response.Code != http.StatusForbidden {
					t.Fatalf("foreign team permission=%d body=%s", response.Code, response.Body.String())
				}
				for _, private := range []string{"私人队长", "私人队员", "联系方式", "暂时无法参加", "3 人", "current"} {
					if strings.Contains(response.Body.String(), private) {
						t.Fatalf("unauthorized write disclosed %q: %s", private, response.Body.String())
					}
				}
			}
		}
	}
	if e.count(`SELECT COUNT(*) FROM registrations WHERE tournament_id=?`, tournament) != 0 {
		t.Fatal("foreign attempt created a registration")
	}
	_, err := e.svc.Submit(e.ctx(captain), SubmitInput{TournamentID: tournament, TeamID: team})
	wantErr(t, err, http.StatusUnprocessableEntity, "私人队员 的资料不完整（缺少联系方式）")
	wantErr(t, err, http.StatusUnprocessableEntity, "私人队员 暂时无法参加赛事报名")
}
