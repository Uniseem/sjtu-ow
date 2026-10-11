package backoffice

import (
	"context"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
)

// BackupStatusReader is supplied by main using the site's own configured backup
// directory. It returns display-safe problem descriptions, never storage keys,
// archive contents, signed object URLs, or an arbitrary filesystem path.
type BackupStatusReader func(context.Context, time.Time) ([]string, error)

func (s *Service) SetBackupStatusReader(reader BackupStatusReader) {
	s.backupStatus = reader
}

// Home gives the existing todo endpoint one shared projection instead of a
// second hand-maintained SQL implementation with drifting table names.
func (s *Service) Home(ctx *app.Ctx) (HomeOut, error) {
	return s.home(ctx, struct{}{})
}
