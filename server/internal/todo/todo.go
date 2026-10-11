package todo

import (
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/backoffice"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type Item struct {
	Text  string `json:"text"`
	URL   string `json:"url"`
	Count int    `json:"count"`
}
type Result struct {
	HasDuties bool   `json:"has_duties"`
	Items     []Item `json:"items"`
}
type Service struct{ d *db.DB }

func NewService(d *db.DB) *Service { return &Service{d: d} }

// The original endpoint keeps its shape while using the completed admin
// home's real schema queries. Database failures are errors, never zero counts.
func (s *Service) GetDuties(ctx *app.Ctx) (*Result, error) {
	out := &Result{Items: []Item{}}
	if ctx.Viewer == nil || ctx.Viewer.Disabled {
		return out, nil
	}
	home, err := backoffice.NewService(s.d, nil).Home(ctx)
	if err != nil {
		return nil, err
	}
	out.HasDuties = home.HasDuties
	for _, item := range home.Todo {
		out.Items = append(out.Items, Item{Text: item.Text, URL: item.URL, Count: item.Count})
	}
	return out, nil
}
