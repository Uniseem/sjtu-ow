package notify

import (
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

const frozenMailCSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'; sandbox"
const frozenErrorCSP = "default-src 'none'; script-src 'none'; style-src 'self'; img-src 'self' data:; font-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'"

var errHeldPreviewMissing = errors.New("frozen letter not found")

// Both legacy bookmark routes and the API document share one actor/batch/id
// check and one frozen renderer, matching core.held_views.letters_preview's
// ownership rule. The old backend did not have an admin single-letter URL.
func (s *Service) frozenPreviewBody(request *http.Request) (string, error) {
	session, err := auth.NewStore(s.d, nil).Lookup(request.Context(), auth.TokenFromRequest(request))
	if err != nil {
		return "", err
	}
	if session == nil {
		return "", errHeldPreviewMissing
	}
	var active int
	err = s.d.ReadPool().QueryRowContext(request.Context(), "SELECT is_active FROM users WHERE id=?", session.UserID).Scan(&active)
	if errors.Is(err, sql.ErrNoRows) || err == nil && active != 1 {
		return "", errHeldPreviewMissing
	}
	if err != nil {
		return "", err
	}
	id, err := strconv.ParseInt(request.PathValue("id"), 10, 64)
	if err != nil || id <= 0 {
		return "", errHeldPreviewMissing
	}
	var frozen, recipients, stamp string
	err = s.d.ReadPool().QueryRowContext(request.Context(), `SELECT letter,recipients,created_at FROM held_letters WHERE id=? AND batch=? AND actor_id=?`, id, request.PathValue("batch"), session.UserID).Scan(&frozen, &recipients, &stamp)
	if errors.Is(err, sql.ErrNoRows) {
		return "", errHeldPreviewMissing
	}
	if err != nil {
		return "", err
	}
	var letter mail.Letter
	if err := json.Unmarshal([]byte(frozen), &letter); err != nil {
		return "", err
	}
	name := ""
	people := parseRecipients(recipients)
	if len(people) > 0 {
		name = people[0].Name
	}
	created, err := db.ParseUTC(stamp)
	if err != nil {
		return "", err
	}
	if created.IsZero() {
		created = time.Now().UTC()
	}
	body, err := letter.HTML(name, s.siteURL, created)
	if err != nil {
		return "", err
	}
	for cid, bytes := range mail.Art() {
		body = strings.ReplaceAll(body, "cid:"+cid, "data:image/png;base64,"+base64.StdEncoding.EncodeToString(bytes))
	}
	return body, nil
}
func (s *Service) serveFrozenPreview(w http.ResponseWriter, request *http.Request, legacy bool) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.Header().Set("X-Frame-Options", "SAMEORIGIN")
	w.Header().Set("Content-Security-Policy", frozenMailCSP)
	body, err := s.frozenPreviewBody(request)
	if errors.Is(err, errHeldPreviewMissing) {
		if legacy {
			// The normal scriptless error page loads error.css; a mail sandbox/style
			// policy must not survive a failure and turn that document into bare text.
			w.Header().Set("Content-Security-Policy", frozenErrorCSP)
			api.LegacyErrorPage(w, http.StatusNotFound)
		} else {
			http.NotFound(w, request)
		}
		return
	}
	if err != nil {
		http.Error(w, "暂时无法打开信件。", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(body))
}

// HeldPreview renders the exact frozen message for the existing API iframe.
func (s *Service) HeldPreview(w http.ResponseWriter, r *http.Request) {
	s.serveFrozenPreview(w, r, false)
}

// LegacyHeldPreview preserves standalone 200 mail documents at old URLs.
func (s *Service) LegacyHeldPreview(w http.ResponseWriter, r *http.Request) {
	s.serveFrozenPreview(w, r, true)
}

// The legacy backend links to the front private preview; this invented SPA URL
// never represented a legacy page and must not reveal a frozen letter.
func (s *Service) MissingLegacyLetterPreview(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.Header().Set("Content-Security-Policy", frozenErrorCSP)
	api.LegacyErrorPage(w, http.StatusNotFound)
}
