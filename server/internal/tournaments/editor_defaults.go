package tournaments

import (
	"github.com/Uniseem/sjtu-ow/server/internal/app"
)

// EditorDefaults is read-only form metadata. It is not an empty database row;
// creating a draft remains the first intentional write performed by the editor.
type EditorDefaults struct {
	Values         EditValues `json:"values"`
	TeamMaxMembers int        `json:"team_max_members"`
}

func (m *Module) editorDefaults(ctx *app.Ctx, _ struct{}) (*EditorDefaults, error) {
	if _, err := requireManager(ctx); err != nil {
		return nil, err
	}
	return &EditorDefaults{
		Values:         EditValues{RegistrationMode: ModeIndividual, RosterMin: 5, RosterMax: 6},
		TeamMaxMembers: teamMaxMembers(ctx.Context, m.svc.d.ReadPool()),
	}, nil
}
