package notify

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
)

const legacyBatchA = "11111111222233334444555555555555"
const canonicalBatchA = "11111111-2222-3333-4444-555555555555"
const legacyFrozen = `{"subject":"Frozen subject","lead":"Frozen original body","paragraphs":["Never rebuilt"],"facts":[["Key","Value"]],"items":[["Details","https://example.invalid/details/"]],"item_link":"Open","code":"","action":["Action","https://example.invalid/action/"],"note":"Original note","reason":"Frozen reason","unsubscribe":"","notice":"Original notice","ignored_old_key":{"kept":"unchanged"}}`
const legacyRecipients = `[["frozen1@example.test","First"],["frozen2@example.test","Second"]]`

type legacyHeldFixture struct {
	id         int64
	actor      int64
	batch      string
	state      string
	created    string
	decided    any
	letter     string
	recipients string
	back       string
	inBack     int
}

func legacyHeldDB(t *testing.T, rows []legacyHeldFixture, schema string) *sql.DB {
	t.Helper()
	path := filepath.Join(t.TempDir(), "legacy-held.sqlite")
	source, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	if schema == "" {
		schema = `CREATE TABLE core_heldletter(id INTEGER PRIMARY KEY,batch TEXT NOT NULL,actor_id INTEGER NOT NULL,letter TEXT NOT NULL,recipients TEXT NOT NULL,back TEXT NOT NULL,in_back_office INTEGER NOT NULL,state TEXT NOT NULL,created_at TEXT NOT NULL,decided_at TEXT)`
	}
	if _, err := source.Exec(schema); err != nil {
		source.Close()
		t.Fatal(err)
	}
	for _, row := range rows {
		if row.letter == "" {
			row.letter = legacyFrozen
		}
		if row.recipients == "" {
			row.recipients = legacyRecipients
		}
		if row.created == "" {
			row.created = t0.Format("2006-01-02 15:04:05.000000")
		}
		if _, err := source.Exec(`INSERT INTO core_heldletter(id,batch,actor_id,letter,recipients,back,in_back_office,state,created_at,decided_at) VALUES(?,?,?,?,?,?,?,?,?,?)`,
			row.id, row.batch, row.actor, row.letter, row.recipients, row.back, row.inBack, row.state, row.created, row.decided); err != nil {
			source.Close()
			t.Fatal(err)
		}
	}
	if err := source.Close(); err != nil {
		t.Fatal(err)
	}
	// The importer sees only a read-only handle, like the real runImport.
	readonly, err := sql.Open("sqlite", "file:"+path+"?mode=ro")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { readonly.Close() })
	return readonly
}

func TestImportHeldLettersKeepsFrozenShapeDatesStatesAndActorIsolation(t *testing.T) {
	e := newEnv(t)
	first := e.user("First actor")
	second := e.user("Second actor")
	oldTime := t0.Add(-8 * 24 * time.Hour).Format("2006-01-02 15:04:05.000000")
	source := legacyHeldDB(t, []legacyHeldFixture{
		{id: 101, actor: first, batch: legacyBatchA, state: "waiting", back: "/teams/7/"},
		{id: 102, actor: first, batch: legacyBatchA, state: "waiting", back: "/admin/scrims/", inBack: 1},
		{id: 103, actor: first, batch: legacyBatchA, state: "sent", decided: "2026-10-09 10:00:00.123456"},
		{id: 104, actor: first, batch: "22222222222222222222222222222222", state: "skipped", decided: "2026-10-09T18:00:00+08:00"},
		{id: 105, actor: first, batch: "33333333333333333333333333333333", state: "waiting", created: oldTime},
		{id: 106, actor: second, batch: "44444444444444444444444444444444", state: "waiting"},
	}, "")
	if err := ImportLegacyHeldLetters(context.Background(), e.d, source); err != nil {
		t.Fatal(err)
	}
	if e.count("SELECT COUNT(*) FROM held_letters") != 6 {
		t.Fatal("did not preserve all source records")
	}
	if e.count("SELECT COUNT(*) FROM jobs WHERE kind=?", outbox.KindLetter) != 0 {
		t.Fatal("import sent or queued frozen letters")
	}
	var batch, created, decided, letter, recipients string
	if err := e.d.ReadPool().QueryRow("SELECT batch,created_at,decided_at,letter,recipients FROM held_letters WHERE id=101").Scan(&batch, &created, &decided, &letter, &recipients); err != nil {
		t.Fatal(err)
	}
	if batch != canonicalBatchA || created != db.FormatUTC(t0) || decided != "" || letter != legacyFrozen || recipients != legacyRecipients {
		t.Fatalf("frozen record rewritten: batch=%s created=%s decided=%s", batch, created, decided)
	}
	if err := e.d.ReadPool().QueryRow("SELECT decided_at FROM held_letters WHERE id=104").Scan(&decided); err != nil {
		t.Fatal(err)
	}
	expected, _ := db.ParseUTC("2026-10-09T18:00:00+08:00")
	if decided != db.FormatUTC(expected) {
		t.Fatalf("decision timezone changed: %s", decided)
	}
	waiting, err := e.svc.Waiting(e.ctxAt(first, t0))
	if err != nil || len(waiting) != 1 || waiting[0].Batch != canonicalBatchA || len(waiting[0].Subjects) != 2 || waiting[0].People != 4 {
		t.Fatalf("owner waiting projection: %+v %v", waiting, err)
	}
	other, err := e.svc.Waiting(e.ctxAt(second, t0))
	if err != nil || len(other) != 1 || other[0].Batch == canonicalBatchA {
		t.Fatalf("actor batches mixed: %+v %v", other, err)
	}
	_, err = e.svc.Held(e.ctxAt(second, t0), canonicalBatchA)
	var apiErr *api.Error
	if !errors.As(err, &apiErr) || apiErr.Status != http.StatusNotFound {
		t.Fatalf("other actor read imported batch: %v", err)
	}
	held, err := e.svc.Held(e.ctxAt(first, t0), canonicalBatchA)
	if err != nil || held.State != "waiting" || len(held.Letters) != 2 || !held.InBackOffice || held.Back != "/admin/scrims/" {
		t.Fatalf("confirmation projection lost metadata: %+v %v", held, err)
	}
	expired, err := e.svc.Held(e.ctxAt(first, t0), "33333333-3333-3333-3333-333333333333")
	if err != nil || expired.State != "expired" || len(expired.Letters) != 0 {
		t.Fatalf("old waiting timestamp refreshed: %+v %v", expired, err)
	}
	// The frozen Python dataclass's JSON is readable by the real Go renderer.
	var frozen mail.Letter
	if err := json.Unmarshal([]byte(letter), &frozen); err != nil {
		t.Fatal(err)
	}
	html, err := frozen.HTML("First", "https://example.invalid", t0)
	if err != nil || !strings.Contains(html, "Frozen original body") || !strings.Contains(html, "Original notice") || !strings.Contains(html, "https://example.invalid/action/") {
		t.Fatalf("legacy letter shape incompatible: %v", err)
	}
}

func TestImportHeldLettersIsIdempotentWithoutResurrectingDecisions(t *testing.T) {
	e := newEnv(t)
	actor := e.user("Actor")
	source := legacyHeldDB(t, []legacyHeldFixture{{id: 1, actor: actor, batch: legacyBatchA, state: "waiting"}, {id: 2, actor: actor, batch: legacyBatchA, state: "waiting"}}, "")
	if err := ImportLegacyHeldLetters(context.Background(), e.d, source); err != nil {
		t.Fatal(err)
	}
	decision, err := e.svc.DecideHeld(e.ctxAt(actor, t0), canonicalBatchA, []int64{1}, false)
	if err != nil || decision.Letters != 1 || decision.People != 2 {
		t.Fatalf("imported letter not sendable: %+v %v", decision, err)
	}
	before := e.count("SELECT COUNT(*) FROM jobs WHERE kind=?", outbox.KindLetter)
	if err := ImportLegacyHeldLetters(context.Background(), e.d, source); err != nil {
		t.Fatal(err)
	}
	if e.count("SELECT COUNT(*) FROM held_letters") != 2 || e.count("SELECT COUNT(*) FROM held_letters WHERE state='waiting'") != 0 {
		t.Fatal("repeat import reset or duplicated decisions")
	}
	if e.count("SELECT COUNT(*) FROM jobs WHERE kind=?", outbox.KindLetter) != before {
		t.Fatal("repeat import queued additional mail")
	}
	if e.count("SELECT COUNT(*) FROM held_letters WHERE id=1 AND state='sent'") != 1 || e.count("SELECT COUNT(*) FROM held_letters WHERE id=2 AND state='skipped'") != 1 {
		t.Fatal("mixed batch decisions not preserved")
	}
	jobs := e.letterJobs()
	if len(jobs) != 2 || jobs["frozen1@example.test"].Lead != "Frozen original body" {
		t.Fatalf("queued letter rebuilt instead of frozen: %+v", jobs)
	}
}

func TestImportHeldLettersRejectsInvalidRowsAtomicallyAndDoesNotEchoRecipients(t *testing.T) {
	scenarios := []struct {
		name string
		row  legacyHeldFixture
	}{
		{"unknown actor", legacyHeldFixture{id: 2, actor: 999, batch: legacyBatchA, state: "waiting"}},
		{"malformed batch", legacyHeldFixture{id: 2, actor: 1, batch: "not-a-uuid", state: "waiting"}},
		{"invalid created", legacyHeldFixture{id: 2, actor: 1, batch: legacyBatchA, state: "waiting", created: "not-a-date"}},
		{"invalid decision", legacyHeldFixture{id: 2, actor: 1, batch: legacyBatchA, state: "sent", decided: "not-a-date"}},
		{"unknown state", legacyHeldFixture{id: 2, actor: 1, batch: legacyBatchA, state: "invented"}},
		{"recipient tuple", legacyHeldFixture{id: 2, actor: 1, batch: legacyBatchA, state: "waiting", recipients: `[["private-address@example.invalid","Name","extra"]]`}},
		{"letter tuple", legacyHeldFixture{id: 2, actor: 1, batch: legacyBatchA, state: "waiting", letter: `{"subject":"Frozen","lead":"Body","facts":[["a","b","extra"]]}`}},
		{"required lead missing", legacyHeldFixture{id: 2, actor: 1, batch: legacyBatchA, state: "waiting", letter: `{"subject":"Frozen"}`}},
	}
	for _, scenario := range scenarios {
		t.Run(scenario.name, func(t *testing.T) {
			e := newEnv(t)
			actor := e.user("Actor")
			first := legacyHeldFixture{id: 1, actor: actor, batch: legacyBatchA, state: "waiting"}
			source := legacyHeldDB(t, []legacyHeldFixture{first, scenario.row}, "")
			err := ImportLegacyHeldLetters(context.Background(), e.d, source)
			if err == nil {
				t.Fatal("invalid source record was silently repaired")
			}
			if strings.Contains(err.Error(), "private-address@example.invalid") || strings.Contains(err.Error(), "Frozen original body") {
				t.Fatalf("import error echoed private frozen contents: %v", err)
			}
			if e.count("SELECT COUNT(*) FROM held_letters") != 0 || e.count("SELECT COUNT(*) FROM jobs WHERE kind=?", outbox.KindLetter) != 0 {
				t.Fatal("partial import or mail queue survived failure")
			}
		})
	}
}

func TestImportHeldLettersRefusesNumericCollisionWithDifferentActor(t *testing.T) {
	e := newEnv(t)
	first := e.user("First")
	second := e.user("Second")
	e.exec("INSERT INTO held_letters(id,batch,actor_id,letter,recipients,state,created_at) VALUES(1,?,?,?,?,?,?)", canonicalBatchA, second, legacyFrozen, legacyRecipients, "waiting", db.FormatUTC(t0))
	source := legacyHeldDB(t, []legacyHeldFixture{{id: 1, actor: first, batch: legacyBatchA, state: "waiting"}}, "")
	if err := ImportLegacyHeldLetters(context.Background(), e.d, source); err == nil {
		t.Fatal("numeric collision was silently ignored")
	}
	if e.count("SELECT COUNT(*) FROM held_letters WHERE id=1 AND actor_id=?", second) != 1 {
		t.Fatal("collision overwrote existing owner")
	}
}

func TestImportHeldLettersMissingTableIsNoopButWrongSchemaIsExplicitError(t *testing.T) {
	e := newEnv(t)
	absent := legacyHeldDB(t, nil, "CREATE TABLE old_unrelated(id INTEGER PRIMARY KEY)")
	if err := ImportLegacyHeldLetters(context.Background(), e.d, absent); err != nil {
		t.Fatal(err)
	}
	wrong := legacyHeldDB(t, nil, "CREATE TABLE core_heldletter(id INTEGER PRIMARY KEY,batch TEXT)")
	if err := ImportLegacyHeldLetters(context.Background(), e.d, wrong); err == nil || !strings.Contains(err.Error(), "actor_id") {
		t.Fatalf("incomplete source schema hidden: %v", err)
	}
	if e.count("SELECT COUNT(*) FROM held_letters") != 0 {
		t.Fatal("missing schema fabricated records")
	}
}

func TestImportHeldUUIDNormalizationPreservesLogicalIdentifier(t *testing.T) {
	for _, source := range []string{legacyBatchA, canonicalBatchA, strings.ToUpper(canonicalBatchA)} {
		actual, err := legacyHeldBatch(source)
		if err != nil || actual != canonicalBatchA {
			t.Fatalf("source=%s actual=%s err=%v", source, actual, err)
		}
	}
	for _, source := range []string{"", "short", strings.Repeat("x", 32), "11111111_2222-3333-4444-555555555555"} {
		if _, err := legacyHeldBatch(source); err == nil {
			t.Fatalf("invalid batch accepted: %s", source)
		}
	}
}

func TestImportHeldCreationCutoffIsInclusiveAtSevenDays(t *testing.T) {
	e := newEnv(t)
	actor := e.user("Actor")
	cutoff := t0.Add(-outbox.Wait)
	source := legacyHeldDB(t, []legacyHeldFixture{
		{id: 1, actor: actor, batch: legacyBatchA, state: "waiting", created: cutoff.Format("2006-01-02 15:04:05.000000")},
		{id: 2, actor: actor, batch: "22222222222222222222222222222222", state: "waiting", created: cutoff.Add(-time.Microsecond).Format("2006-01-02 15:04:05.000000")},
	}, "")
	if err := ImportLegacyHeldLetters(context.Background(), e.d, source); err != nil {
		t.Fatal(err)
	}
	waiting, err := e.svc.Waiting(e.ctxAt(actor, t0))
	if err != nil || len(waiting) != 1 || waiting[0].Batch != canonicalBatchA {
		t.Fatalf("cutoff semantics changed: %+v %v", waiting, err)
	}
}
