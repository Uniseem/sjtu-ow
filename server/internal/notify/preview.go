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

	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

// HeldPreview renders the exact frozen message, not an editable or inferred
// body. Raw routes enforce authentication here because they bypass JSON gates.
func (s *Service) HeldPreview(w http.ResponseWriter, request *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.Header().Set("X-Frame-Options", "SAMEORIGIN")
	w.Header().Set("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'; sandbox")
	session, err := auth.NewStore(s.d, nil).Lookup(request.Context(), auth.TokenFromRequest(request))
	if err != nil {
		http.Error(w, "暂时无法打开信件。", http.StatusInternalServerError)
		return
	}
	if session == nil {
		http.NotFound(w, request)
		return
	}
	var active int
	err = s.d.ReadPool().QueryRowContext(request.Context(), `SELECT is_active FROM users WHERE id=?`, session.UserID).Scan(&active)
	if errors.Is(err, sql.ErrNoRows) || err == nil && active != 1 {
		http.NotFound(w, request)
		return
	}
	if err != nil {
		http.Error(w, "暂时无法打开信件。", http.StatusInternalServerError)
		return
	}
	id, err := strconv.ParseInt(request.PathValue("id"), 10, 64)
	if err != nil || id <= 0 {
		http.NotFound(w, request)
		return
	}
	var frozen, recipients, stamp string
	err = s.d.ReadPool().QueryRowContext(request.Context(),
		`SELECT letter,recipients,created_at FROM held_letters WHERE id=? AND batch=? AND actor_id=?`,
		id, request.PathValue("batch"), session.UserID).Scan(&frozen, &recipients, &stamp)
	if errors.Is(err, sql.ErrNoRows) {
		http.NotFound(w, request)
		return
	}
	if err != nil {
		http.Error(w, "暂时无法打开信件。", http.StatusInternalServerError)
		return
	}
	var letter mail.Letter
	if err := json.Unmarshal([]byte(frozen), &letter); err != nil {
		http.Error(w, "信件暂时无法读取。", http.StatusInternalServerError)
		return
	}
	name := ""
	people := parseRecipients(recipients)
	if len(people) > 0 {
		name = people[0].Name
	}
	created, err := db.ParseUTC(stamp)
	if err != nil {
		http.Error(w, "信件时间无效。", http.StatusInternalServerError)
		return
	}
	if created.IsZero() {
		created = time.Now().UTC()
	}
	body, err := letter.HTML(name, s.siteURL, created)
	if err != nil {
		http.Error(w, "信件暂时无法读取。", http.StatusInternalServerError)
		return
	}
	for cid, bytes := range mail.Art() {
		body = strings.ReplaceAll(body, "cid:"+cid,
			"data:image/png;base64,"+base64.StdEncoding.EncodeToString(bytes))
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(body))
}
