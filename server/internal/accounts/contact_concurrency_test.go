package accounts

import (
	"context"
	"errors"
	"sync"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestConcurrentContactCreationReturnsFieldRejection(t *testing.T) {
	database, _, _, _, ctx := personalPatchFixture(t)
	service := NewService(database, nil, "https://example.invalid", nil, nil)
	const attempts = 8
	results := make(chan error, attempts)
	var pending sync.WaitGroup
	start := make(chan struct{})
	for index := 0; index < attempts; index++ {
		pending.Add(1)
		go func() {
			defer pending.Done()
			<-start
			_, err := service.AddContact(ctx, AddContactInput{Type: "qq", Value: "123456789"})
			results <- err
		}()
	}
	close(start)
	pending.Wait()
	close(results)
	successes := 0
	for err := range results {
		if err == nil {
			successes++
			continue
		}
		var problem *api.Error
		if !errors.As(err, &problem) || problem.Status != 422 || len(problem.Fields["type"]) != 1 {
			t.Fatalf("concurrent duplicate should be an ordinary field error: %v", err)
		}
	}
	if successes != 1 {
		t.Fatalf("created %d contacts", successes)
	}
	var count int
	if err := database.ReadPool().QueryRowContext(context.Background(), `SELECT COUNT(*) FROM contacts WHERE user_id=? AND type='qq'`, ctx.Viewer.ID).Scan(&count); err != nil || count != 1 {
		t.Fatalf("persisted contacts=%d err=%v", count, err)
	}
}

func TestContactCreationRechecksAfterAnotherTabCommits(t *testing.T) {
	_, service, clock, _, ctx := personalPatchFixture(t)
	clock.hook = func() {
		if _, err := service.AddContact(ctx, AddContactInput{Type: "qq", Value: "123456789"}); err != nil {
			t.Fatal(err)
		}
	}
	_, err := service.AddContact(ctx, AddContactInput{Type: "qq", Value: "123456789"})
	personalPatchStatus(t, err, 422)
}

func TestContactCreationCannotRestoreDataAfterAccountDisabled(t *testing.T) {
	database, service, clock, owner, ctx := personalPatchFixture(t)
	clock.hook = func() {
		if err := database.WriteTx(context.Background(), func(txCtx context.Context, tx *db.Tx) error {
			_, err := tx.ExecContext(txCtx, `UPDATE users SET is_active=0 WHERE id=?`, owner.ID)
			return err
		}); err != nil {
			t.Fatal(err)
		}
	}
	_, err := service.AddContact(ctx, AddContactInput{Type: "qq", Value: "123456789"})
	personalPatchStatus(t, err, 401)
	var count int
	if err := database.ReadPool().QueryRow(`SELECT COUNT(*) FROM contacts WHERE user_id=?`, owner.ID).Scan(&count); err != nil || count != 0 {
		t.Fatalf("inactive account data reappeared: count=%d err=%v", count, err)
	}
}
