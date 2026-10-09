package activity

import (
	"fmt"
	"net/http"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// Module 负责活动数据路由。
type Module struct {
	svc *Service
}

// NewModule 创建活动数据模块。
func NewModule(svc *Service) *Module {
	return &Module{svc: svc}
}

// GetActivityIn 是 GET /api/admin/activity 的入参。
type GetActivityIn struct {
	Preset string `query:"preset"`
	Start  string `query:"start"`
	End    string `query:"end"`
}

// GetActivityOut 是 GET /api/admin/activity 的响应。
type GetActivityOut struct {
	Period  Period   `json:"period"`
	Notice  string   `json:"notice,omitempty"`
	Totals  Totals   `json:"totals"`
	Events  []Event  `json:"events"`
	Presets []string `json:"presets"`
}

// Routes 注册活动数据路由。
func (m *Module) Routes(r *api.Registry) {
	api.Get(r, "/api/admin/activity", api.Cap(accounts.CapActivityView), m.getActivity,
		api.Nav("data", "activity"))
	api.Raw(r, http.MethodGet, "/api/admin/activity/export", nil, m.exportCSV)
}

func (m *Module) getActivity(ctx *app.Ctx, in GetActivityIn) (GetActivityOut, error) {
	period, notice := DatesToPeriod(in.Preset, in.Start, in.End, ctx.Now())

	events, err := m.svc.QueryEvents(ctx.Context, period)
	if err != nil {
		return GetActivityOut{}, err
	}

	totals, err := m.svc.QueryTotals(ctx.Context, period, events)
	if err != nil {
		return GetActivityOut{}, err
	}

	return GetActivityOut{
		Period:  period,
		Notice:  notice,
		Totals:  totals,
		Events:  events,
		Presets: []string{"this_year", "last_year", "recent_30"},
	}, nil
}

func (m *Module) exportCSV(w http.ResponseWriter, r *http.Request) {
	preset := r.URL.Query().Get("preset")
	startStr := r.URL.Query().Get("start")
	endStr := r.URL.Query().Get("end")

	period, _ := DatesToPeriod(preset, startStr, endStr, time.Now())
	events, err := m.svc.QueryEvents(r.Context(), period)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	data, err := GenerateCSV(events)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	filename := fmt.Sprintf("activity-%s-%s.csv", period.Start.Format("2006-01-02"), period.End.Format("2006-01-02"))
	w.Header().Set("Content-Type", "text/csv; charset=utf-8")
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=\"%s\"", filename))
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(data)
}
