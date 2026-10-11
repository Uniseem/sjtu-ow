package fonts

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type fontEnv struct {
	service        *Service
	ctx            *app.Ctx
	d              *db.DB
	media, uploads string
}

func newFontEnv(t *testing.T) *fontEnv {
	t.Helper()
	directory := t.TempDir()
	d, err := db.Open(filepath.Join(directory, "test.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { d.Close() })
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatal(err)
	}
	now := time.Date(2026, 10, 11, 12, 0, 0, 0, time.UTC)
	err = d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		for _, user := range []struct {
			id    int
			email string
		}{{1, "admin@example.test"}, {2, "other@example.test"}} {
			if _, err := tx.ExecContext(ctx, `INSERT INTO users(id,email,email_norm,password_hash,nickname,is_sjtu,agreed_terms_at,agreed_cross_border_at,email_verified_at,is_superuser,created_at,updated_at) VALUES(?,?,?,'disabled-test-hash','测试管理员',1,?,?,?,1,?,?)`, user.id, user.email, user.email, stamp(now), stamp(now), stamp(now), stamp(now), stamp(now)); err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	media := filepath.Join(directory, "media")
	uploads := filepath.Join(directory, "private-fontuploads")
	return &fontEnv{service: NewService(d, media, uploads), ctx: &app.Ctx{Context: context.Background(), Clock: clock.Fixed(now), Viewer: &app.Viewer{ID: 1, Superuser: true}}, d: d, media: media, uploads: uploads}
}

// Structural parser unit fixture, deliberately not a glyph-rendering fixture.
// Real WOFF2 decoding and pixels belong to the browser/legacy-media acceptance.
func woff2Envelope() []byte {
	data := make([]byte, 64)
	copy(data, "wOF2")
	binary.BigEndian.PutUint32(data[4:8], 0x00010000)
	binary.BigEndian.PutUint32(data[8:12], uint32(len(data)))
	binary.BigEndian.PutUint16(data[12:14], 1)
	binary.BigEndian.PutUint32(data[16:20], 128)
	binary.BigEndian.PutUint32(data[20:24], 16)
	return data
}
func packageFixture(t *testing.T, change func(*Manifest), extras map[string][]byte) []byte {
	t.Helper()
	font := woff2Envelope()
	manifest := Manifest{Version: 1, Family: "Fixture Sans", DisplayName: "结构测试字体", License: "OFL test fixture", LicenseConfirmed: true, Faces: []Face{{Weight: 400, Style: "normal", Bytes: int64(len(font)), Slices: []Slice{{Path: "slices/400.woff2", UnicodeRange: "U+20-7E", SHA256: digest(font), Bytes: int64(len(font))}}}}}
	if change != nil {
		change(&manifest)
	}
	var buffer bytes.Buffer
	writer := zip.NewWriter(&buffer)
	raw, err := json.Marshal(manifest)
	if err != nil {
		t.Fatal(err)
	}
	files := map[string][]byte{"manifest.json": raw, "slices/400.woff2": font}
	for name, data := range extras {
		files[name] = data
	}
	for name, data := range files {
		file, err := writer.Create(name)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := file.Write(data); err != nil {
			t.Fatal(err)
		}
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	return buffer.Bytes()
}
func apiStatus(t *testing.T, err error, want int) {
	t.Helper()
	var problem *api.Error
	if !errors.As(err, &problem) || problem.Status != want {
		t.Fatalf("error=%v; want API %d", err, want)
	}
}
func importFixture(t *testing.T, env *fontEnv) FontDetail {
	t.Helper()
	result, err := env.service.importFont(env.ctx, ImportIn{Source: "package", PackageName: "fixture.zip", PackageBase64: base64.StdEncoding.EncodeToString(packageFixture(t, nil, nil)), LicenseConfirmed: true})
	if err != nil {
		t.Fatal(err)
	}
	return result
}

func TestPackageRejectsTraversalAndManifestCorruption(t *testing.T) {
	cases := []struct {
		name   string
		change func(*Manifest)
		extra  map[string][]byte
	}{
		{"path traversal", nil, map[string][]byte{"../outside.woff2": woff2Envelope()}},
		{"absolute path", nil, map[string][]byte{"/outside.woff2": woff2Envelope()}},
		{"unlisted payload", nil, map[string][]byte{"other.woff2": woff2Envelope()}},
		{"wrong sha256", func(m *Manifest) { m.Faces[0].Slices[0].SHA256 = strings.Repeat("0", 64) }, nil},
		{"wrong byte length", func(m *Manifest) { m.Faces[0].Slices[0].Bytes++ }, nil},
		{"CSS injection", func(m *Manifest) { m.Faces[0].Slices[0].UnicodeRange = "U+20; src:url(https://example.test/x)" }, nil},
		{"duplicate face", func(m *Manifest) { m.Faces = append(m.Faces, m.Faces[0]) }, nil},
		{"missing license", func(m *Manifest) { m.LicenseConfirmed = false }, nil},
		{"unknown version", func(m *Manifest) { m.Version = 99 }, nil},
	}
	for _, item := range cases {
		t.Run(item.name, func(t *testing.T) {
			_, err := preparePackage(packageFixture(t, item.change, item.extra))
			if err == nil {
				t.Fatal("unsafe package accepted")
			}
		})
	}
}
func TestPackageUnknownFieldsAndTrailingJSONRejected(t *testing.T) {
	var buffer bytes.Buffer
	archive := zip.NewWriter(&buffer)
	file, err := archive.Create("manifest.json")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := file.Write([]byte(`{"version":1,"system_key":"not permitted"}`)); err != nil {
		t.Fatal(err)
	}
	if err := archive.Close(); err != nil {
		t.Fatal(err)
	}
	if _, err := preparePackage(buffer.Bytes()); err == nil {
		t.Fatal("unknown manifest field accepted")
	}
}
func TestPackageImportWritesOnlyVerifiedObjectsAndDeduplicates(t *testing.T) {
	env := newFontEnv(t)
	first := importFixture(t, env)
	second := importFixture(t, env)
	if first.Font.ID != second.Font.ID {
		t.Fatalf("identical package created %d and %d", first.Font.ID, second.Font.ID)
	}
	if first.Font.Slices != 1 || first.Font.Bytes != 64 {
		t.Fatalf("bad metadata: %+v", first.Font)
	}
	data, err := os.ReadFile(filepath.Join(env.media, "fonts", "objects", digest(woff2Envelope())+".woff2"))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(data, woff2Envelope()) {
		t.Fatal("stored bytes differ")
	}
	var count int
	if err := env.d.ReadPool().QueryRow(`SELECT COUNT(*) FROM font_families`).Scan(&count); err != nil {
		t.Fatal(err)
	}
	if count != 1 {
		t.Fatalf("families=%d", count)
	}
}
func TestFailedPackageDoesNotPersistMetadataOrObjects(t *testing.T) {
	env := newFontEnv(t)
	corrupted := packageFixture(t, func(m *Manifest) { m.Faces[0].Slices[0].SHA256 = "bad" }, nil)
	_, err := env.service.importFont(env.ctx, ImportIn{Source: "package", PackageBase64: base64.StdEncoding.EncodeToString(corrupted), LicenseConfirmed: true})
	apiStatus(t, err, 400)
	var count int
	if err := env.d.ReadPool().QueryRow(`SELECT COUNT(*) FROM font_families`).Scan(&count); err != nil {
		t.Fatal(err)
	}
	if count != 0 {
		t.Fatal("failed import left metadata")
	}
	if _, err := os.Stat(filepath.Join(env.media, "fonts")); !os.IsNotExist(err) {
		t.Fatalf("failed import wrote objects: %v", err)
	}
}
func TestChunkUploadOwnerBoundaryReplayAndExpiredCleanup(t *testing.T) {
	env := newFontEnv(t)
	content := bytes.Repeat([]byte{7}, ChunkBytes+19)
	upload, err := env.service.beginUpload(env.ctx, BeginUploadIn{Name: "font.zip", TotalBytes: int64(len(content)), LicenseConfirmed: true})
	if err != nil {
		t.Fatal(err)
	}
	other := *env.ctx
	other.Viewer = &app.Viewer{ID: 2, Superuser: true}
	chunk := UploadChunkIn{ID: api.ID(upload.ID), Offset: 0, DataBase64: base64.StdEncoding.EncodeToString(content[:ChunkBytes])}
	if _, err := env.service.uploadChunk(&other, chunk); err == nil {
		t.Fatal("other superuser wrote owner's upload")
	} else {
		apiStatus(t, err, 404)
	}
	if _, err := env.service.uploadChunk(env.ctx, chunk); err != nil {
		t.Fatal(err)
	}
	if _, err := env.service.uploadChunk(env.ctx, chunk); err != nil {
		t.Fatalf("exact chunk replay failed: %v", err)
	}
	different := chunk
	different.DataBase64 = base64.StdEncoding.EncodeToString(bytes.Repeat([]byte{9}, ChunkBytes))
	if _, err := env.service.uploadChunk(env.ctx, different); err == nil {
		t.Fatal("different replay overwrote chunk")
	}
	if _, err := env.service.assembledUpload(env.ctx, upload.ID); err == nil {
		t.Fatal("incomplete upload assembled")
	}
	tail := UploadChunkIn{ID: api.ID(upload.ID), Offset: ChunkBytes, DataBase64: base64.StdEncoding.EncodeToString(content[ChunkBytes:])}
	if _, err := env.service.uploadChunk(env.ctx, tail); err != nil {
		t.Fatal(err)
	}
	assembled, err := env.service.assembledUpload(env.ctx, upload.ID)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(assembled, content) {
		t.Fatal("assembled upload differs")
	}
	sentinel := filepath.Join(env.media, "keep.txt")
	if err := os.MkdirAll(env.media, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(sentinel, []byte("keep"), 0644); err != nil {
		t.Fatal(err)
	}
	count, err := env.service.CleanupExpired(context.Background(), env.ctx.Now().Add(2*time.Hour))
	if err != nil {
		t.Fatal(err)
	}
	if count != 1 {
		t.Fatalf("cleanup=%d", count)
	}
	if _, err := os.Stat(sentinel); err != nil {
		t.Fatalf("cleanup touched media: %v", err)
	}
	var uploads int
	if err := env.d.ReadPool().QueryRow(`SELECT COUNT(*) FROM font_uploads`).Scan(&uploads); err != nil {
		t.Fatal(err)
	}
	if uploads != 0 {
		t.Fatal("expired upload record retained")
	}
}
func TestTypographyAtomicValidationConflictAndReferencedFontDeletion(t *testing.T) {
	env := newFontEnv(t)
	font := importFixture(t, env)
	page, err := env.service.typography(env.ctx)
	if err != nil {
		t.Fatal(err)
	}
	if len(page.Regions) != 9 {
		t.Fatalf("regions=%d", len(page.Regions))
	}
	invalid := append([]Region{}, page.Regions...)
	invalid[0].Mode = "inherit"
	if _, err := env.service.patchTypography(env.ctx, PatchTypographyIn{BaseVersion: page.Version, Changes: TypographyChanges{Regions: &invalid}}); err == nil {
		t.Fatal("body inherit accepted")
	}
	current, err := env.service.typography(env.ctx)
	if err != nil {
		t.Fatal(err)
	}
	if current.Version != page.Version || current.Regions[0].Mode != "system" {
		t.Fatal("invalid patch partly committed")
	}
	regions := append([]Region{}, page.Regions...)
	regions[0].Mode = "custom"
	regions[0].FamilyID = &font.Font.ID
	receipt, err := env.service.patchTypography(env.ctx, PatchTypographyIn{BaseVersion: page.Version, Changes: TypographyChanges{Regions: &regions}})
	if err != nil {
		t.Fatal(err)
	}
	if receipt.Version != page.Version+1 {
		t.Fatalf("version=%d", receipt.Version)
	}
	cssPath, err := env.service.CSSPointer(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	css, err := os.ReadFile(filepath.Join(env.media, strings.TrimPrefix(cssPath, "/media/")))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(css), "@font-face") || !strings.Contains(string(css), "--font-body:") {
		t.Fatalf("missing CSS: %s", css)
	}
	if _, err := env.service.patchTypography(env.ctx, PatchTypographyIn{BaseVersion: page.Version, Changes: TypographyChanges{Regions: &regions}}); err == nil {
		t.Fatal("stale patch accepted")
	} else {
		apiStatus(t, err, 409)
	}
	if _, err := env.service.delete(env.ctx, font.Font.ID); err == nil {
		t.Fatal("referenced font deleted")
	} else {
		apiStatus(t, err, 422)
	}
	regions[0].Mode = "system"
	regions[0].FamilyID = nil
	if _, err := env.service.patchTypography(env.ctx, PatchTypographyIn{BaseVersion: receipt.Version, Changes: TypographyChanges{Regions: &regions}}); err != nil {
		t.Fatal(err)
	}
	if _, err := env.service.delete(env.ctx, font.Font.ID); err != nil {
		t.Fatal(err)
	}
	// Deleting metadata must retain immutable objects referenced by already-loaded CSS.
	if _, err := os.Stat(filepath.Join(env.media, "fonts", "objects", digest(woff2Envelope())+".woff2")); err != nil {
		t.Fatal(err)
	}
}
func TestTypographyPreviewCannotAlterGlobalVariablesOrStoredState(t *testing.T) {
	env := newFontEnv(t)
	page, err := env.service.typography(env.ctx)
	if err != nil {
		t.Fatal(err)
	}
	preview, err := env.service.preview(env.ctx, PreviewIn{Regions: page.Regions})
	if err != nil {
		t.Fatal(err)
	}
	css, err := os.ReadFile(filepath.Join(env.media, strings.TrimPrefix(preview.CSSPath, "/media/")))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(css), ":root {") || !strings.Contains(string(css), "#typography-preview {") {
		t.Fatal("preview CSS affects global root")
	}
	after, err := env.service.typography(env.ctx)
	if err != nil {
		t.Fatal(err)
	}
	if after.Version != page.Version || after.CSSPath != page.CSSPath {
		t.Fatal("preview changed saved typography")
	}
}
func TestFontRoutesRejectVisitorsAndOtherRolesBeforeHandlers(t *testing.T) {
	registry := &api.Registry{}
	NewModule(NewService(nil, "", "")).Routes(registry)
	for _, route := range registry.Routes() {
		target := strings.ReplaceAll(route.Pattern, "{id}", "1")
		for _, viewer := range []*app.Viewer{nil, {ID: 1}} {
			handler := registry.Handler(func(*http.Request) *app.Viewer { return viewer })
			request := httptest.NewRequest(route.Method, target, strings.NewReader(`{}`))
			request.Header.Set("Content-Type", "application/json")
			recorder := httptest.NewRecorder()
			handler.ServeHTTP(recorder, request)
			want := 403
			if viewer == nil {
				want = 401
			}
			if recorder.Code != want {
				t.Fatalf("%s %s got=%d want=%d body=%s", route.Method, target, recorder.Code, want, recorder.Body.String())
			}
		}
	}
}
