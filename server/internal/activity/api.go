package activity

import (
	"fmt"
	"net/http"
	"net/url"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// Module 负责活动数据路由。
type Module struct {
	svc      *Service
	resolver api.ViewerResolver
}

// NewModule 创建活动数据模块。
func NewModule(svc *Service) *Module {
	return &Module{svc: svc}
}

// SetViewerResolver uses the same session resolver as the JSON API registry.
func (m *Module) SetViewerResolver(resolve api.ViewerResolver) { m.resolver = resolve }

// GetActivityIn 是 GET /api/admin/activity 的入参。
type GetActivityIn struct {
	Preset string `query:"preset"`
	Start  string `query:"start"`
	End    string `query:"end"`
}

// GetActivityOut 是 GET /api/admin/activity 的响应。
type GetActivityOut struct {
	ExportURL string   `json:"export_url"`
	Period    Period   `json:"period"`
	Notice    string   `json:"notice,omitempty"`
	Totals    Totals   `json:"totals"`
	Events    []Event  `json:"events"`
	Presets   []string `json:"presets"`
}

// Routes 注册活动数据路由。
func (m *Module) Routes(r *api.Registry) {
	api.Get(r, "/api/admin/activity", api.Cap(accounts.CapActivityView), m.getActivity,
		api.Nav("data", "activity"))
	api.Raw(r, http.MethodGet, "/api/admin/activity/export", nil, m.exportCSV)
	api.Raw(r, http.MethodGet, "/admin/activity/{$}", nil, m.legacyExportCSV)
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
		ExportURL: "/admin/activity/?" + url.Values{"format": {"csv"}, "start": {period.Start.Format("2006-01-02")}, "end": {period.End.Format("2006-01-02")}}.Encode(),
		Period:    period,
		Notice:    notice,
		Totals:    totals,
		Events:    events,
		Presets:   []string{"this_year", "last_year", "recent_30"},
	}, nil
}

func (m *Module) exportCSV(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "private, no-store")
	var viewer *app.Viewer
	if m.resolver != nil {
		viewer = m.resolver(r)
	}
	if viewer == nil || viewer.Disabled || viewer.ID <= 0 {
		http.Error(w, "要先登录", http.StatusUnauthorized)
		return
	}
	if !viewer.HasCap(accounts.CapActivityView) {
		http.Error(w, "没有权限", http.StatusForbidden)
		return
	}

	preset := r.URL.Query().Get("preset")
	startStr := r.URL.Query().Get("start")
	endStr := r.URL.Query().Get("end")

	period, _ := DatesToPeriod(preset, startStr, endStr, time.Now())
	events, err := m.svc.QueryEvents(r.Context(), period)
	if err != nil {
		http.Error(w, "暂时无法导出。", http.StatusInternalServerError)
		return
	}

	data, err := GenerateCSV(events)
	if err != nil {
		http.Error(w, "暂时无法导出。", http.StatusInternalServerError)
		return
	}

	filename := fmt.Sprintf("activity-%s-%s.csv", period.Start.Format("2006-01-02"), period.End.Format("2006-01-02"))
	w.Header().Set("Content-Type", "text/csv; charset=utf-8")
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=\"%s\"", filename))
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(data)
}

func (m *Module) legacyExportCSV(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "private, no-store")
	w.Header().Set("Vary", "Cookie")
	if r.URL.Query().Get("format") != "csv" {
		api.LegacyErrorPage(w, http.StatusNotFound)
		return
	}
	var viewer *app.Viewer
	if m.resolver != nil {
		viewer = m.resolver(r)
	}
	if viewer == nil || viewer.Disabled || viewer.ID <= 0 {
		http.Redirect(w, r, "/accounts/login/?next="+url.QueryEscape(r.URL.RequestURI()), http.StatusFound)
		return
	}
	if !viewer.HasCap(accounts.CapActivityView) {
		api.LegacyErrorPage(w, http.StatusForbidden)
		return
	}
	m.exportCSV(w, r)
}
