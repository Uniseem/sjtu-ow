package fonts

import (
	"context"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func blobPath() string { return "fonts/objects/" + digest(woff2Envelope()) + ".woff2" }
func assertBlob(t *testing.T, env *fontEnv, path string, exists bool) {
	t.Helper()
	_, err := os.Stat(filepath.Join(env.media, filepath.FromSlash(path)))
	if exists && err != nil {
		t.Fatalf("expected object: %v", err)
	}
	if !exists && !os.IsNotExist(err) {
		t.Fatalf("object retained/unknown stat: %v", err)
	}
}
func faceID(t *testing.T, env *fontEnv, family int64) int64 {
	t.Helper()
	var id int64
	if err := env.d.ReadPool().QueryRow("SELECT id FROM font_faces WHERE family_id=?", family).Scan(&id); err != nil {
		t.Fatal(err)
	}
	return id
}
func claimCount(t *testing.T, env *fontEnv) int {
	t.Helper()
	var count int
	if err := env.d.ReadPool().QueryRow("SELECT COUNT(*) FROM font_blob_claims").Scan(&count); err != nil {
		t.Fatal(err)
	}
	return count
}
func TestFontBlobDeletionRetainsSharedObjectAndRemovesLastReference(t *testing.T) {
	env := newFontEnv(t)
	first := importFixture(t, env)
	second, err := env.service.importFont(env.ctx, ImportIn{Source: "package", LicenseConfirmed: true, PackageBase64: base64.StdEncoding.EncodeToString(packageFixture(t, func(m *Manifest) { m.Family = "Second Family" }, nil))})
	if err != nil {
		t.Fatal(err)
	}
	if claimCount(t, env) != 0 {
		t.Fatal("successful import retained lease")
	}
	cssPath := "fonts/css/current-test.css"
	cssBytes := []byte("/* current stylesheet remains immutable */")
	if err := env.service.writeBlob(cssPath, cssBytes); err != nil {
		t.Fatal(err)
	}
	foreignPath := filepath.Join(env.media, "fonts", "foreign-font.woff2")
	if err := os.WriteFile(foreignPath, []byte("leave this alone"), 0644); err != nil {
		t.Fatal(err)
	}
	if _, err := env.service.deleteFace(env.ctx, faceID(t, env, first.Font.ID)); err != nil {
		t.Fatal(err)
	}
	assertBlob(t, env, blobPath(), true)
	if _, err := env.service.delete(env.ctx, second.Font.ID); err != nil {
		t.Fatal(err)
	}
	assertBlob(t, env, blobPath(), false)
	got, err := os.ReadFile(filepath.Join(env.media, cssPath))
	if err != nil || string(got) != string(cssBytes) {
		t.Fatal("font deletion altered CSS")
	}
	if _, err := os.Stat(foreignPath); err != nil {
		t.Fatal("font deletion touched foreign object")
	}
}
func TestFontBlobImportLeaseProtectsPreparedObjectAcrossLastFaceDeletion(t *testing.T) {
	env := newFontEnv(t)
	font := importFixture(t, env)
	lease, err := newBlobLease()
	if err != nil {
		t.Fatal(err)
	}
	if err := env.service.claimBlobPaths(env.ctx.Context, lease, []string{blobPath()}, env.ctx.Now()); err != nil {
		t.Fatal(err)
	}
	if _, err := env.service.delete(env.ctx, font.Font.ID); err != nil {
		t.Fatal(err)
	}
	assertBlob(t, env, blobPath(), true)
	if err := env.service.releaseBlobClaims(env.ctx.Context, lease, env.ctx.Now()); err != nil {
		t.Fatal(err)
	}
	assertBlob(t, env, blobPath(), false)
	if claimCount(t, env) != 0 {
		t.Fatal("released lease retained")
	}
}
func TestFontBlobFailedMetadataImportReleasesClaimsAndOnlyItsUnusedObjects(t *testing.T) {
	env := newFontEnv(t)
	existing := importFixture(t, env)
	// The package validates and writes successfully but its family mismatches the
	// destination. This hits failure after acquiring leases, not a parser failure.
	_, err := env.service.importFont(env.ctx, ImportIn{FamilyID: existing.Font.ID, Source: "package", LicenseConfirmed: true, PackageBase64: base64.StdEncoding.EncodeToString(packageFixture(t, func(m *Manifest) { m.Family = "Different Family" }, nil))})
	if err == nil {
		t.Fatal("mismatched target family accepted")
	}
	if claimCount(t, env) != 0 {
		t.Fatal("failed import leaked claims")
	}
	assertBlob(t, env, blobPath(), true)
	// A nonexistent target leaves no metadata reference and must reclaim its blob.
	other := newFontEnv(t)
	_, err = other.service.importFont(other.ctx, ImportIn{FamilyID: 99999, Source: "package", LicenseConfirmed: true, PackageBase64: base64.StdEncoding.EncodeToString(packageFixture(t, nil, nil))})
	if err == nil {
		t.Fatal("missing target accepted")
	}
	if claimCount(t, other) != 0 {
		t.Fatal("failure retained lease")
	}
	assertBlob(t, other, blobPath(), false)
}
func TestFontBlobExpiredClaimsCleanupKeepsOtherImportLease(t *testing.T) {
	env := newFontEnv(t)
	first, err := newBlobLease()
	if err != nil {
		t.Fatal(err)
	}
	if err := env.service.claimBlobPaths(env.ctx.Context, first, []string{blobPath()}, env.ctx.Now()); err != nil {
		t.Fatal(err)
	}
	if err := env.service.writeBlob(blobPath(), woff2Envelope()); err != nil {
		t.Fatal(err)
	}
	second, err := newBlobLease()
	if err != nil {
		t.Fatal(err)
	}
	if err := env.service.claimBlobPaths(env.ctx.Context, second, []string{blobPath()}, env.ctx.Now().Add(time.Hour)); err != nil {
		t.Fatal(err)
	}
	if _, err := env.service.CleanupExpired(env.ctx.Context, env.ctx.Now().Add(24*time.Hour)); err != nil {
		t.Fatal(err)
	}
	if claimCount(t, env) != 1 {
		t.Fatal("cleanup erased active import's lease")
	}
	assertBlob(t, env, blobPath(), true)
	if _, err := env.service.CleanupExpired(env.ctx.Context, env.ctx.Now().Add(25*time.Hour)); err != nil {
		t.Fatal(err)
	}
	assertBlob(t, env, blobPath(), false)
}
func TestFontBlobPublishAfterConcurrentDeletionCannotLoseClaimedFile(t *testing.T) {
	env := newFontEnv(t)
	font := importFixture(t, env)
	lease, err := newBlobLease()
	if err != nil {
		t.Fatal(err)
	}
	if err := env.service.claimBlobPaths(env.ctx.Context, lease, []string{blobPath()}, env.ctx.Now()); err != nil {
		t.Fatal(err)
	}
	// Model the actual import phases: writer lease -> outside-lock blob write ->
	// metadata publication. Deletion may run after the file write and before publish.
	written := make(chan struct{})
	deleted := make(chan struct{})
	errors := make(chan error, 2)
	var group sync.WaitGroup
	group.Add(2)
	go func() {
		defer group.Done()
		err := env.service.writeBlob(blobPath(), woff2Envelope())
		errors <- err
		close(written)
		<-deleted
		err = env.d.WriteTx(context.Background(), func(c context.Context, tx *db.Tx) error {
			slices, _ := json.Marshal([]Slice{{Path: blobPath(), SHA256: digest(woff2Envelope()), Bytes: int64(len(woff2Envelope()))}})
			_, err := tx.ExecContext(c, `INSERT INTO font_families(id,family,display_name,css_name,source,source_ref,license,license_confirmed,created_at) VALUES(999,'Published','Published','new-claim-family','package','','test',1,?)`, stamp(env.ctx.Now()))
			if err != nil {
				return err
			}
			_, err = tx.ExecContext(c, "INSERT INTO font_faces(family_id,weight,style,slices,bytes) VALUES(999,400,'normal',?,?)", string(slices), len(woff2Envelope()))
			return err
		})
		errors <- err
	}()
	go func() {
		defer group.Done()
		<-written
		_, err := env.service.delete(env.ctx, font.Font.ID)
		if err != nil {
			t.Error(err)
		}
		close(deleted)
	}()
	group.Wait()
	close(errors)
	for err := range errors {
		if err != nil {
			t.Fatal(err)
		}
	}
	if err := env.service.releaseBlobClaims(env.ctx.Context, lease, env.ctx.Now()); err != nil {
		t.Fatal(err)
	}
	assertBlob(t, env, blobPath(), true)
}
func TestFontBlobCleanupRejectsUnsafePathsAndSymlinkObjects(t *testing.T) {
	env := newFontEnv(t)
	lease, err := newBlobLease()
	if err != nil {
		t.Fatal(err)
	}
	if err := env.service.claimBlobPaths(env.ctx.Context, lease, []string{"../outside.woff2"}, env.ctx.Now()); err == nil {
		t.Fatal("unsafe lease path accepted")
	}
	root := t.TempDir()
	external := filepath.Join(root, "outside.woff2")
	if err := os.WriteFile(external, []byte("external"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(env.media, "fonts/objects"), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(external, filepath.Join(env.media, blobPath())); err != nil {
		t.Fatal(err)
	}
	if err := env.service.cleanupBlobPaths(env.ctx.Context, []string{blobPath(), "fonts/css/current.css", strings.Repeat("a", 64) + ".woff2"}, env.ctx.Now()); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(external)
	if err != nil || string(data) != "external" {
		t.Fatal("external symlink target changed")
	}
	if _, err := os.Lstat(filepath.Join(env.media, blobPath())); err != nil {
		t.Fatal("symlink was removed")
	}
}

func TestLegacyFontImportFailureReleasesOnlyNewObjectClaims(t *testing.T) {
	env := newFontEnv(t)
	legacy, err := sql.Open("sqlite", filepath.Join(t.TempDir(), "legacy.sqlite"))
	if err != nil {
		t.Fatal(err)
	}
	defer legacy.Close()
	for _, query := range []string{
		`CREATE TABLE core_fontfamily(id INTEGER PRIMARY KEY,name TEXT,css_name TEXT,source TEXT,source_ref TEXT,license_type TEXT,license_note TEXT,license_confirmed INTEGER,created_by_id INTEGER,created_at TEXT)`,
		`CREATE TABLE core_fontface(id INTEGER PRIMARY KEY,family_id INTEGER,weight INTEGER,style TEXT,status TEXT,error TEXT,slices TEXT)`,
		`INSERT INTO core_fontfamily VALUES(100,'Old font','old-font','upload','source.ttf','other','Test license',1,1,'2026-10-11T12:00:00Z')`,
	} {
		if _, err := legacy.Exec(query); err != nil {
			t.Fatal(err)
		}
	}
	oldMedia := t.TempDir()
	source := "fonts/old/source.woff2"
	if err := os.MkdirAll(filepath.Dir(filepath.Join(oldMedia, source)), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(oldMedia, source), woff2Envelope(), 0600); err != nil {
		t.Fatal(err)
	}
	slices, _ := json.Marshal([]Slice{{Path: source, UnicodeRange: "U+20-7E"}, {Path: "fonts/old/missing.woff2", UnicodeRange: "U+80-FF"}})
	if _, err := legacy.Exec("INSERT INTO core_fontface VALUES(200,100,400,'normal','ready','',?)", string(slices)); err != nil {
		t.Fatal(err)
	}
	if _, err := ImportLegacyFonts(context.Background(), env.d, legacy, oldMedia, env.media); err == nil {
		t.Fatal("missing legacy slice accepted")
	}
	if claimCount(t, env) != 0 {
		t.Fatal("legacy failure retained claim")
	}
	assertBlob(t, env, blobPath(), false)
	sourceBytes, err := os.ReadFile(filepath.Join(oldMedia, source))
	if err != nil || digest(sourceBytes) != digest(woff2Envelope()) {
		t.Fatal("legacy source modified")
	}
	var families int
	if err := env.d.ReadPool().QueryRow("SELECT COUNT(*) FROM font_families").Scan(&families); err != nil || families != 0 {
		t.Fatal("partial legacy font metadata persisted")
	}
}
