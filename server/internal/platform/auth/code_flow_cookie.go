package auth

import (
	"net/http"
	"time"
)

const SignupFlowCookieName = "ow_signup_flow"
const ResetCodeFlowCookieName = "ow_reset_code_flow"

func codeFlowName(purpose string) string {
	switch purpose {
	case "signup":
		return SignupFlowCookieName
	case "password_reset":
		return ResetCodeFlowCookieName
	default:
		return ""
	}
}
func CodeFlowTokensFromRequest(r *http.Request) map[string]string {
	tokens := map[string]string{}
	for _, purpose := range []string{"signup", "password_reset"} {
		if cookie, err := r.Cookie(codeFlowName(purpose)); err == nil {
			tokens[purpose] = cookie.Value
		}
	}
	return tokens
}

// Anonymous opaque tokens use the same private cookie policy as reset grants.
func SetCodeFlowCookie(w http.ResponseWriter, purpose, token string, expires, now time.Time, secure bool) {
	name := codeFlowName(purpose)
	if name == "" {
		return
	}
	age := int(expires.Sub(now).Seconds())
	if token == "" || age <= 0 {
		token = ""
		age = -1
	}
	http.SetCookie(w, &http.Cookie{Name: name, Value: token, Path: "/", MaxAge: age, Expires: expires, HttpOnly: true, Secure: secure, SameSite: http.SameSiteLaxMode})
}
