package tournaments

import (
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// EditValues is deliberately restricted to the editable fields. A receipt and
// a conflict use the same shape; neither leaks unrelated row internals.
type EditValues struct {
	Title                string     `json:"title"`
	Summary              string     `json:"summary"`
	Description          string     `json:"description"`
	CoverImageID         *int64     `json:"cover_image_id"`
	StartsAt             *time.Time `json:"starts_at"`
	RegistrationOpensAt  *time.Time `json:"registration_opens_at"`
	RegistrationClosesAt *time.Time `json:"registration_closes_at"`
	RosterMin            int        `json:"roster_min"`
	RosterMax            int        `json:"roster_max"`
	SjtuOnly             bool       `json:"sjtu_only"`
	RegistrationMode     string     `json:"registration_mode"`
	AutoApprove          bool       `json:"auto_approve"`
	ParticipantContact   string     `json:"participant_contact"`
}

type EditCurrent struct {
	Version int64      `json:"version"`
	Values  EditValues `json:"values"`
}

func editValues(t *Tournament) EditValues {
	return EditValues{
		Title: t.Title, Summary: t.Summary, Description: t.Description,
		CoverImageID: t.CoverImageID, StartsAt: t.StartsAt,
		RegistrationOpensAt:  t.RegistrationOpensAt,
		RegistrationClosesAt: t.RegistrationClosesAt,
		RosterMin:            t.RosterMin, RosterMax: t.RosterMax,
		SjtuOnly: t.SjtuOnly, RegistrationMode: t.RegistrationMode,
		AutoApprove: t.AutoApprove, ParticipantContact: t.ParticipantContact,
	}
}

func editConflict(t *Tournament) *api.Error {
	e := api.NewErr(409, "stale", "另一个人刚改过，已换成最新内容")
	e.Current = EditCurrent{Version: t.Version, Values: editValues(t)}
	return e
}

// acknowledgeEdit includes valid unchanged fields. A normalized title that
// equals the old title has still been accepted; omitting it would tell the
// browser that a successful no-op was a field failure.
func acknowledgeEdit(ch Changes, result *SaveResult, t *Tournament) {
	provided := []struct {
		name    string
		present bool
	}{
		{"title", ch.Title != nil},
		{"summary", ch.Summary != nil},
		{"description", ch.Description != nil},
		{"cover_image_id", ch.CoverImageID != nil},
		{"remove_cover", ch.RemoveCover != nil},
		{"starts_at", ch.StartsAt != nil},
		{"registration_opens_at", ch.RegistrationOpensAt != nil},
		{"registration_closes_at", ch.RegistrationClosesAt != nil},
		{"roster_min", ch.RosterMin != nil},
		{"roster_max", ch.RosterMax != nil},
		{"sjtu_only", ch.SjtuOnly != nil},
		{"registration_mode", ch.RegistrationMode != nil},
		{"auto_approve", ch.AutoApprove != nil},
		{"participant_contact", ch.ParticipantContact != nil},
	}
	blocked := map[string]bool{}
	for name, messages := range result.Fields {
		if len(messages) > 0 {
			blocked[name] = true
		}
	}
	for _, group := range [][]string{
		{"registration_opens_at", "registration_closes_at"},
		{"roster_min", "roster_max"},
	} {
		if blocked[group[0]] || blocked[group[1]] {
			for _, name := range group {
				blocked[name] = true
			}
		}
	}
	result.Saved = []string{}
	for _, item := range provided {
		if item.present && !blocked[item.name] {
			result.Saved = append(result.Saved, item.name)
		}
	}
	result.Values = editValues(t)
}

// CopyPreview applies the exact same week displacement as Copy without
// inserting a row or recording a mutation. The source id remains addressable.
func (s *Service) CopyPreview(ctx *app.Ctx, id int64) (*AdminDetail, error) {
	detail, err := s.AdminGet(ctx, id)
	if err != nil {
		return nil, err
	}
	copy := *detail.Tournament
	shift := weeksAhead([]*time.Time{copy.StartsAt, copy.RegistrationOpensAt, copy.RegistrationClosesAt}, ctx.Now().UTC())
	move := func(value *time.Time) *time.Time {
		if value == nil {
			return nil
		}
		moved := value.Add(shift)
		return &moved
	}
	copy.StartsAt = move(copy.StartsAt)
	copy.RegistrationOpensAt = move(copy.RegistrationOpensAt)
	copy.RegistrationClosesAt = move(copy.RegistrationClosesAt)
	copy.Status = StatusDraft
	copy.PublishedAt = nil
	copy.ReminderSentAt = nil
	copy.MovedFrom = nil
	copy.Version = 0
	copy.CreatedBy = nil
	detail.Tournament = &copy
	detail.Missing = Missing(&copy)
	if detail.Missing == nil {
		detail.Missing = []string{}
	}
	detail.HasEntries = false
	detail.HasRegs = false
	detail.CanDelete = false
	return detail, nil
}
