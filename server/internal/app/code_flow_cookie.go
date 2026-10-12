package app

import "time"

type CodeFlowCookie struct {
	Purpose   string
	Token     string
	ExpiresAt time.Time
}

func (c *Ctx) SetCodeFlowCookie(purpose, token string, expires time.Time) {
	c.codeFlowCookies = append(c.codeFlowCookies, CodeFlowCookie{Purpose: purpose, Token: token, ExpiresAt: expires})
}
func (c *Ctx) DrainCodeFlowCookies() []CodeFlowCookie {
	out := c.codeFlowCookies
	c.codeFlowCookies = nil
	return out
}
