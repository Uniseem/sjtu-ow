package scrims

import (
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// EditValues is the saved, normalized value of every editable field.
type EditValues struct {
	Title          string     `json:"title"`
	Description    string     `json:"description"`
	StartsAt       *time.Time `json:"starts_at"`
	SignupClosesAt *time.Time `json:"signup_closes_at"`
	Format         string     `json:"format"`
	SjtuOnly       bool       `json:"sjtu_only"`
}

type EditCurrent struct {
	Version int64      `json:"version"`
	Values  EditValues `json:"values"`
}

func editValues(sc *Scrim) EditValues {
	return EditValues{
		Title: sc.Title, Description: sc.Description,
		StartsAt: sc.StartsAt, SignupClosesAt: sc.SignupClosesAt,
		Format: sc.Format, SjtuOnly: sc.SjtuOnly,
	}
}

func editConflict(sc *Scrim) *api.Error {
	e := api.NewErr(409, "stale", "另一个人刚改过，已换成最新内容")
	e.Current = EditCurrent{Version: sc.Version, Values: editValues(sc)}
	return e
}

func acknowledgeEdit(ch Changes, result *SaveResult, sc *Scrim) {
	provided := []struct {
		name    string
		present bool
	}{
		{"title", ch.Title != nil},
		{"description", ch.Description != nil},
		{"starts_at", ch.StartsAt != nil},
		{"signup_closes_at", ch.SignupClosesAt != nil},
		{"format", ch.Format != nil},
		{"sjtu_only", ch.SjtuOnly != nil},
	}
	result.Saved = []string{}
	for _, item := range provided {
		if item.present && len(result.Fields[item.name]) == 0 {
			result.Saved = append(result.Saved, item.name)
		}
	}
	result.Values = editValues(sc)
}

// CopyPreview does not create drafts on GET. The POST remains the sole writer.
func (s *Service) CopyPreview(ctx *app.Ctx, id int64) (*AdminGetOut, error) {
	_, original, err := s.AdminGet(ctx, id)
	if err != nil {
		return nil, err
	}
	copy := *original
	shift := weeksAhead([]*time.Time{copy.StartsAt, copy.SignupClosesAt}, ctx.Now().UTC())
	move := func(value *time.Time) *time.Time {
		if value == nil {
			return nil
		}
		moved := value.Add(shift)
		return &moved
	}
	copy.StartsAt = move(copy.StartsAt)
	copy.SignupClosesAt = move(copy.SignupClosesAt)
	copy.Status = StatusDraft
	copy.TeamsGeneratedAt = nil
	copy.RosterChangedAt = nil
	copy.ReminderSentAt = nil
	copy.MovedFrom = nil
	copy.Version = 0
	copy.BoardVersion = 0
	copy.CreatedBy = nil
	missing := Missing(&copy)
	if missing == nil {
		missing = []string{}
	}
	row := &AdminRow{Card: cardOf(&copy, 0, ctx.Now().UTC()), Missing: missing}
	return &AdminGetOut{Scrim: &copy, Row: row}, nil
}
