package db

import (
	"context"
	"log/slog"
)

// recordHandler 接住警告日志，测试断言「记了警告但没拦事务」用。
type recordHandler struct{ warns int }

func (h *recordHandler) Enabled(_ context.Context, l slog.Level) bool { return l >= slog.LevelWarn }

func (h *recordHandler) Handle(_ context.Context, r slog.Record) error {
	if r.Level >= slog.LevelWarn {
		h.warns++
	}
	return nil
}

func (h *recordHandler) WithAttrs([]slog.Attr) slog.Handler { return h }

func (h *recordHandler) WithGroup(string) slog.Handler { return h }

// setSlogHandler 换掉默认 logger 的 handler，返回原来的。
func setSlogHandler(h slog.Handler) slog.Handler {
	old := slog.Default().Handler()
	slog.SetDefault(slog.New(h))
	return old
}
