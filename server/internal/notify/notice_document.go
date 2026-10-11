package notify

import (
	"context"
	"encoding/base64"
	"errors"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

// SetViewerBuilder gives raw preview documents the same current permission
// projection as JSON endpoints. The callback avoids a notifier-to-domain import.
func (s *Service) SetViewerBuilder(builder func(context.Context, int64) (*app.Viewer, error)) {
	s.viewers = builder
}

func noticePreviewURL(kind string, id int64, audience, note, version string, publishing ...bool) string {
	query := url.Values{}
	query.Set("to", audience)
	query.Set("note", note)
	query.Set("version", version)
	if len(publishing) > 0 && publishing[0] {
		query.Set("publishing", "1")
	}
	return "/api/admin/announce/" + url.PathEscape(kind) + "/" + strconv.FormatInt(id, 10) + "/preview?" + query.Encode()
}

// NoticeDocument isolates mail.HTML's paper styling from the SPA's strict CSP.
// It never renders a client-supplied HTML body and does not mutate the database.
func (s *Service) NoticeDocument(w http.ResponseWriter, request *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.Header().Set("X-Frame-Options", "SAMEORIGIN")
	w.Header().Set("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'; sandbox")
	if s.viewers == nil {
		http.Error(w, "暂时无法预览通知。", http.StatusServiceUnavailable)
		return
	}
	session, err := auth.NewStore(s.d, nil).Lookup(request.Context(), auth.TokenFromRequest(request))
	if err != nil {
		http.Error(w, "暂时无法预览通知。", http.StatusInternalServerError)
		return
	}
	if session == nil {
		http.NotFound(w, request)
		return
	}
	viewer, err := s.viewers(request.Context(), session.UserID)
	if err != nil {
		http.Error(w, "暂时无法预览通知。", http.StatusInternalServerError)
		return
	}
	if viewer == nil || viewer.Disabled {
		http.NotFound(w, request)
		return
	}
	id, err := strconv.ParseInt(request.PathValue("id"), 10, 64)
	if err != nil || id <= 0 {
		http.NotFound(w, request)
		return
	}
	version := request.URL.Query().Get("version")
	parts := strings.Split(version, ".")
	if len(parts) != 2 {
		http.NotFound(w, request)
		return
	}
	expires, err := strconv.ParseInt(parts[0], 10, 64)
	ctx := &app.Ctx{Context: request.Context(), Viewer: viewer}
	if err != nil || expires <= ctx.Now().Unix() || expires > ctx.Now().Add(15*time.Minute).Unix() {
		http.Error(w, "通知预览已失效，请刷新预览。", http.StatusConflict)
		return
	}
	q, err := s.d.ReadPool().BeginTx(request.Context(), nil)
	if err != nil {
		http.Error(w, "暂时无法预览通知。", http.StatusInternalServerError)
		return
	}
	defer q.Rollback()
	draft, err := s.makeNoticeDraft(ctx, q, request.PathValue("kind"), id,
		request.URL.Query().Get("to"), request.URL.Query().Get("note"), expires, request.URL.Query().Get("publishing") == "1")
	if err != nil {
		var failure *api.Error
		if errors.As(err, &failure) && (failure.Status == 403 || failure.Status == 404 || failure.Status == 401) {
			http.NotFound(w, request)
			return
		}
		http.Error(w, "暂时无法预览通知。", http.StatusInternalServerError)
		return
	}
	if draft.preview.PreviewVersion != version {
		http.Error(w, "通知内容或收件人有变化，请刷新预览。", http.StatusConflict)
		return
	}
	body := draft.preview.BodyHTML
	for cid, bytes := range mail.Art() {
		body = strings.ReplaceAll(body, "cid:"+cid, "data:image/png;base64,"+base64.StdEncoding.EncodeToString(bytes))
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(body))
}
