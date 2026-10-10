package auth

import (
	"math"
	"net/http"
	"time"
)

const ResetCookieName = "ow_password_reset"

// A password-reset grant is separate from login and never exposes a session.
func ResetTokenFromRequest(r *http.Request) string {
	c, err := r.Cookie(ResetCookieName)
	if err != nil {
		return ""
	}
	return c.Value
}

func SetResetCookie(w http.ResponseWriter, token string, expires, now time.Time, secure bool) {
	maxAge := int(math.Ceil(expires.Sub(now).Seconds()))
	if token == "" || maxAge <= 0 {
		maxAge = -1
		token = ""
	}
	http.SetCookie(w, &http.Cookie{
		Name: ResetCookieName, Value: token, Path: "/", MaxAge: maxAge, Expires: expires,
		HttpOnly: true, Secure: secure, SameSite: http.SameSiteLaxMode,
	})
}
