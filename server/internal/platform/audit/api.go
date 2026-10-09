package audit

import (
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Module 负责审计日志路由注册。
type Module struct {
	d *db.DB
}

// NewModule 创建审计日志模块。
func NewModule(d *db.DB) *Module {
	return &Module{d: d}
}

// ListLogIn 是 GET /api/admin/log 的入参。
type ListLogIn struct {
	Action     string `query:"action"`
	ActorID    *int64 `query:"actor_id"`
	ObjectType string `query:"object_type"`
	Since      string `query:"since"`
	Until      string `query:"until"`
	Page       int    `query:"page"`
	PageSize   int    `query:"page_size"`
}

// ListLogOut 是 GET /api/admin/log 的出参。
type ListLogOut = QueryResult

// Routes 注册审计日志路由。
func (m *Module) Routes(r *api.Registry) {
	api.Get(r, "/api/admin/log", api.Superuser, m.list, api.Nav("settings", "log"))
}

func (m *Module) list(ctx *app.Ctx, in ListLogIn) (ListLogOut, error) {
	var sinceTime, untilTime *time.Time
	if in.Since != "" {
		if t, err := time.Parse(time.RFC3339, in.Since); err == nil {
			sinceTime = &t
		} else if t, err := time.Parse("2006-01-02", in.Since); err == nil {
			sinceTime = &t
		}
	}
	if in.Until != "" {
		if t, err := time.Parse(time.RFC3339, in.Until); err == nil {
			untilTime = &t
		} else if t, err := time.Parse("2006-01-02", in.Until); err == nil {
			t = t.Add(24 * time.Hour)
			untilTime = &t
		}
	}

	qIn := QueryInput{
		Action:     in.Action,
		ActorID:    in.ActorID,
		ObjectType: in.ObjectType,
		Since:      sinceTime,
		Until:      untilTime,
		Page:       in.Page,
		PageSize:   in.PageSize,
	}

	res, err := Query(ctx.Context, m.d.ReadPool(), qIn)
	if err != nil {
		return ListLogOut{}, err
	}
	return *res, nil
}
