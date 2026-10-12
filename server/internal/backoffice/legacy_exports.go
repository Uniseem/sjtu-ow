package backoffice

import (
	"errors"
	"net/http"
	"net/url"
	"strconv"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// SetViewerResolver makes bookmarked downloads share the JSON API session gate.
func (m *Module) SetViewerResolver(resolve api.ViewerResolver) { m.resolver = resolve }

func (m *Module) legacyExportRoutes(registry *api.Registry) {
	api.Raw(registry, http.MethodGet, "/admin/registrations/export.csv", nil, m.legacyRegistrationCSV)
}

func (m *Module) legacyRegistrationCSV(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "private, no-store")
	w.Header().Set("Vary", "Cookie")
	var viewer *app.Viewer
	if m.resolver != nil {
		viewer = m.resolver(r)
	}
	if viewer == nil || viewer.Disabled || viewer.ID <= 0 {
		http.Redirect(w, r, "/accounts/login/?next="+url.QueryEscape(r.URL.RequestURI()), http.StatusFound)
		return
	}
	query := r.URL.Query()
	status := "pending"
	if query.Has("status") {
		status = query.Get("status")
	}
	tournament, _ := strconv.ParseInt(query.Get("tournament"), 10, 64)
	if tournament < 0 {
		tournament = 0
	}
	ctx := &app.Ctx{Context: r.Context(), Viewer: viewer}
	result, err := m.svc.exportRegistrations(ctx, RegistrationQuery{Status: status, TournamentID: tournament})
	if err != nil {
		var problem *api.Error
		if errors.As(err, &problem) && problem.Status < 500 {
			if problem.Status == http.StatusForbidden || problem.Status == http.StatusNotFound {
				api.LegacyErrorPage(w, problem.Status)
			} else {
				http.Error(w, problem.Message, problem.Status)
			}
		} else {
			http.Error(w, "暂时无法导出。", http.StatusInternalServerError)
		}
		return
	}
	w.Header().Set("Content-Type", "text/csv; charset=utf-8")
	w.Header().Set("Content-Disposition", `attachment; filename="`+result.Filename+`"`)
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(result.CSV))
}
