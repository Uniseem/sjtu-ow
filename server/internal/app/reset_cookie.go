package app

import "time"

type ResetCookie struct {
	Token     string
	ExpiresAt time.Time
}

func (c *Ctx) SetResetCookie(token string, expires time.Time) {
	c.resetCookie = &ResetCookie{Token: token, ExpiresAt: expires}
}
func (c *Ctx) ClearResetCookie()              { c.resetCookie = &ResetCookie{} }
func (c *Ctx) DrainResetCookie() *ResetCookie { out := c.resetCookie; c.resetCookie = nil; return out }
