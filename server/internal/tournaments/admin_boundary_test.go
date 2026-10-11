package tournaments

import (
	"errors"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/notify"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
)

func TestPoolSnapshotBlocksNewSignupBeforeBoardSave(t *testing.T) {
	e := newEnv(t)
	id := e.tour(withMode(ModeIndividual))
	first, second := e.user("先报名"), e.user("后报名")
	if _, err := e.svc.SignUpIndividual(e.ctx(first), SignupInput{TournamentID: id, GameAccountID: e.firstAccount(first), Roles: []string{"tank"}}); err != nil {
		t.Fatal(err)
	}
	board, err := e.svc.GetBoard(e.mgr(), id)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := e.svc.SignUpIndividual(e.ctx(second), SignupInput{TournamentID: id, GameAccountID: e.firstAccount(second), Roles: []string{"support"}}); err != nil {
		t.Fatal(err)
	}
	_, err = e.svc.FormTeams(e.mgr(), id, []LayoutTeam{{Name: "新队", SignupIDs: []int64{board.Entries[0].SignupID}}}, board.PoolVersion)
	var stale *api.Error
	if !errors.As(err, &stale) || stale.Status != 409 {
		t.Fatalf("old pool accepted: %v", err)
	}
	if e.count(`SELECT COUNT(*) FROM registrations WHERE tournament_id=?`, id) != 0 {
		t.Fatal("stale compilation created a partial team")
	}
	if e.count(`SELECT COUNT(*) FROM individual_signups WHERE tournament_id=? AND registration_id IS NULL`, id) != 2 {
		t.Fatal("stale compilation removed people from their pool")
	}
}

func TestCopyPreviewDoesNotCreateAndConflictCarriesNormalizedValues(t *testing.T) {
	e := newEnv(t)
	id := e.tour(withStart(t0.Add(-24*time.Hour)), withWindow(t0.Add(-48*time.Hour), t0.Add(-time.Hour)))
	before := e.count(`SELECT COUNT(*) FROM tournaments`)
	preview, err := e.svc.CopyPreview(e.mgr(), id)
	if err != nil {
		t.Fatal(err)
	}
	if e.count(`SELECT COUNT(*) FROM tournaments`) != before {
		t.Fatal("copy preview created a draft")
	}
	if preview.Tournament.Version != 0 || preview.Tournament.Status != StatusDraft || !preview.Tournament.RegistrationOpensAt.After(t0) {
		t.Fatalf("copy preview not shifted to future: %+v", preview.Tournament)
	}
	original, err := GetTournament(e.mgr().Context, e.d.ReadPool(), id)
	if err != nil {
		t.Fatal(err)
	}
	if original.Status != StatusPublished || !original.StartsAt.Before(t0) {
		t.Fatal("copy preview mutated original")
	}
	result, err := e.svc.UpdateTournament(e.mgr(), id, original.Version, Changes{Title: str("  春季赛  ")})
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Saved) != 1 || result.Saved[0] != "title" || result.Values.Title != "春季赛" {
		t.Fatalf("normalized no-op rejected: %+v", result)
	}
	_, err = e.svc.UpdateTournament(e.mgr(), id, original.Version+9, Changes{Title: str("覆盖")})
	var stale *api.Error
	if !errors.As(err, &stale) || stale.Status != 409 || stale.Current == nil {
		t.Fatalf("conflict omitted safe current values: %v", err)
	}
}

func TestPublicationNoticeFailureRollsBackPublication(t *testing.T) {
	e := newEnv(t)
	id := e.tour(withStatus(StatusDraft))
	notifier := notify.NewService(e.d, "https://sjtu.example", "test-signing-key", func() bool { return true })
	notifier.Register(e.svc.AnnounceKind())
	e.svc.SetNotifier(notifier)
	module := NewModule(e.svc)
	preview, err := module.publishPreview(e.mgr(), IDIn{ID: api.ID(id)})
	if err != nil {
		t.Fatal(err)
	}
	if preview.Problem != "" {
		t.Fatalf("ready publication refused: %s", preview.Problem)
	}
	// The recipient set changes after approval; publication and email insertion
	// must both roll back instead of publishing and reporting an email failure.
	e.user("后来加入")
	_, err = module.publishNotice(e.mgr(), PublishNoticeIn{ID: api.ID(id), Announce: true, PreviewVersion: preview.PreviewVersion})
	if err == nil {
		t.Fatal("changed recipient approval accepted")
	}
	item, err := GetTournament(e.mgr().Context, e.d.ReadPool(), id)
	if err != nil {
		t.Fatal(err)
	}
	if item.Status != StatusDraft {
		t.Fatal("notification rejection left publication committed")
	}
	if e.count(`SELECT COUNT(*) FROM broadcasts`) != 0 || e.count(`SELECT COUNT(*) FROM jobs WHERE kind=?`, outbox.KindLetter) != 0 {
		t.Fatal("notification rejection wrote broadcast or mail")
	}
	fresh, err := module.publishPreview(e.mgr(), IDIn{ID: api.ID(id)})
	if err != nil {
		t.Fatal(err)
	}
	result, err := module.publishNotice(e.mgr(), PublishNoticeIn{ID: api.ID(id), Announce: true, PreviewVersion: fresh.PreviewVersion})
	if err != nil {
		t.Fatal(err)
	}
	if result.Tournament.Status != StatusPublished || result.Notice == nil || result.Notice.Recipients != 2 {
		t.Fatalf("atomic confirmed publish failed: %+v", result)
	}
}
