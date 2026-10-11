package scrims

import "github.com/Uniseem/sjtu-ow/server/internal/app"

// EditorDefaults carries defaults without manufacturing a persisted object.
type EditorDefaults struct {
	Values EditValues `json:"values"`
}

func (m *Module) editorDefaults(ctx *app.Ctx, _ struct{}) (*EditorDefaults, error) {
	if _, err := requireManager(ctx); err != nil {
		return nil, err
	}
	return &EditorDefaults{Values: EditValues{Format: FormatRQ5}}, nil
}
