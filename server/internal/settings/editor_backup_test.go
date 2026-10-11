package settings

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/crypto"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

const editorFieldKey = "settings-test-field-key-no-real-secret"

type editorEnv struct {
	t       *testing.T
	d       *db.DB
	service *Service
	module  *Module
	ctx     *app.Ctx
}

func newEditorEnv(t *testing.T) *editorEnv {
	t.Helper()
	database := newTestDB(t)
	service := NewService(database, "https://site.example.test", editorFieldKey)
	return &editorEnv{t: t, d: database, service: service, module: NewModule(service), ctx: &app.Ctx{Context: context.Background(), Clock: clock.Fixed(time.Date(2026, 10, 11, 12, 0, 0, 0, time.UTC)), Viewer: &app.Viewer{ID: 1, Nickname: "站长", Superuser: true}}}
}
func (e *editorEnv) exec(query string, args ...any) {
	e.t.Helper()
	if err := e.d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error { _, err := tx.ExecContext(ctx, query, args...); return err }); err != nil {
		e.t.Fatal(err)
	}
}
func (e *editorEnv) column(query string) string {
	e.t.Helper()
	var value string
	if err := e.d.ReadPool().QueryRow(query).Scan(&value); err != nil {
		e.t.Fatal(err)
	}
	return value
}
func assertEditorStatus(t *testing.T, err error, want int) {
	t.Helper()
	var failure *api.Error
	if !errors.As(err, &failure) || failure.Status != want {
		t.Fatalf("error=%v want=%d", err, want)
	}
}
func jsonWithoutSecrets(t *testing.T, value any, secrets ...string) string {
	t.Helper()
	raw, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	body := string(raw)
	for _, secret := range secrets {
		if secret != "" && strings.Contains(body, secret) {
			t.Fatalf("JSON revealed sensitive test value; response=%s", body)
		}
	}
	return body
}
func (e *editorEnv) request(method, path, body string, viewer *app.Viewer) *httptest.ResponseRecorder {
	e.t.Helper()
	registry := &api.Registry{}
	e.module.Routes(registry)
	handler := registry.Handler(func(*http.Request) *app.Viewer { return viewer })
	request := httptest.NewRequest(method, path, strings.NewReader(body))
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	return response
}

func TestEditorVersionedPartialSaveKeepsInvalidAndUnsubmittedFields(t *testing.T) {
	e := newEditorEnv(t)
	old, err := e.service.Get(e.ctx.Context)
	if err != nil {
		t.Fatal(err)
	}
	description := "  社团介绍  "
	port := 0
	saved, err := e.service.patchFields(e.ctx, &old.Version, SettingsChanges{SiteDescription: &description, SmtpPort: &port})
	if err != nil {
		t.Fatal(err)
	}
	if saved.Version != old.Version+1 || len(saved.Saved) != 1 || saved.Saved[0] != "site_description" || len(saved.Fields["smtp_port"]) == 0 {
		t.Fatalf("receipt=%+v", saved)
	}
	if saved.Values.SiteDescription != "社团介绍" || saved.Values.SmtpPort != old.SmtpPort {
		t.Fatal("partial save changed rejected field or missed normalization")
	}
	if saved.Values.FromName != old.FromName || saved.Values.TeamMaxMembers != old.TeamMaxMembers {
		t.Fatal("partial save reset unrelated settings")
	}
	var audit map[string]any
	if err := json.Unmarshal([]byte(e.column(`SELECT data FROM audit_log WHERE action='site_settings.update' ORDER BY id DESC LIMIT 1`)), &audit); err != nil {
		t.Fatal(err)
	}
	fields, ok := audit["fields"].([]any)
	if !ok || len(fields) != 1 || fields[0] != "site_description" {
		t.Fatalf("audit=%v", audit)
	}
	rejectedVersion := saved.Version
	invalidAddress := "not-an-email"
	rejected, err := e.service.patchFields(e.ctx, &rejectedVersion, SettingsChanges{FromAddress: &invalidAddress})
	if err != nil {
		t.Fatal(err)
	}
	if rejected.Version != rejectedVersion || len(rejected.Saved) != 0 || len(rejected.Fields["from_address"]) == 0 {
		t.Fatal("entirely invalid request incremented version or reported success")
	}
}
func TestEditorConflictProjectionNeverContainsStoredSecrets(t *testing.T) {
	e := newEditorEnv(t)
	smtpSecret, aiSecret := "smtp-secret-for-test", "ai-secret-for-test"
	configured, err := e.service.Update(e.ctx, UpdateSettingsInput{SmtpPassword: &smtpSecret, ModerationAPIKey: &aiSecret})
	if err != nil {
		t.Fatal(err)
	}
	stale := configured.Version - 1
	description := "不应覆盖"
	_, err = e.service.patchFields(e.ctx, &stale, SettingsChanges{SiteDescription: &description})
	assertEditorStatus(t, err, 409)
	var failure *api.Error
	if !errors.As(err, &failure) || failure.Current == nil {
		t.Fatal("409 omitted current safe projection")
	}
	storedSMTP := e.column(`SELECT smtp_password FROM site_settings WHERE id=1`)
	storedAI := e.column(`SELECT moderation_api_key FROM site_settings WHERE id=1`)
	jsonWithoutSecrets(t, failure.Current, smtpSecret, aiSecret, storedSMTP, storedAI)
	if e.column(`SELECT site_description FROM site_settings WHERE id=1`) == description {
		t.Fatal("stale description committed")
	}
	response := e.request(http.MethodPatch, "/api/admin/settings", `{"base_version":1,"changes":{"site_description":"old request"}}`, e.ctx.Viewer)
	if response.Code != 409 {
		t.Fatalf("conflict HTTP=%d body=%s", response.Code, response.Body.String())
	}
	var wire map[string]any
	if err := json.Unmarshal(response.Body.Bytes(), &wire); err != nil {
		t.Fatal(err)
	}
	if _, present := wire["current"]; !present {
		t.Fatal("wire error omitted current")
	}
	jsonWithoutSecrets(t, wire, smtpSecret, aiSecret, storedSMTP, storedAI)
}
func TestEditorImageZeroClearsButMissingImageFieldDoesNot(t *testing.T) {
	e := newEditorEnv(t)
	e.exec(`INSERT INTO images(id,title,file_name,file_size,width,height,created_at) VALUES(801,'图片','fixture.webp',20,100,100,'2026-10-11T00:00:00Z')`)
	old, err := e.service.Get(e.ctx.Context)
	if err != nil {
		t.Fatal(err)
	}
	image := int64(801)
	first, err := e.service.patchFields(e.ctx, &old.Version, SettingsChanges{HeroImageID: &image})
	if err != nil {
		t.Fatal(err)
	}
	if first.Values.HeroImageID == nil || *first.Values.HeroImageID != 801 {
		t.Fatal("existing image was not selected")
	}
	description := "只改说明"
	second, err := e.service.patchFields(e.ctx, &first.Version, SettingsChanges{SiteDescription: &description})
	if err != nil {
		t.Fatal(err)
	}
	if second.Values.HeroImageID == nil || *second.Values.HeroImageID != 801 {
		t.Fatal("missing image field cleared image")
	}
	zero := int64(0)
	cleared, err := e.service.patchFields(e.ctx, &second.Version, SettingsChanges{HeroImageID: &zero})
	if err != nil {
		t.Fatal(err)
	}
	if cleared.Values.HeroImageID != nil {
		t.Fatal("zero image id did not clear reference")
	}
	nonexistent := int64(999)
	rejected, err := e.service.patchFields(e.ctx, &cleared.Version, SettingsChanges{HeroImageID: &nonexistent})
	if err != nil {
		t.Fatal(err)
	}
	if len(rejected.Fields["hero_image_id"]) == 0 || rejected.Version != cleared.Version {
		t.Fatal("unknown image accepted or invalid request committed")
	}
}
func TestEditorSecretExplicitKeepClearAndAuditContainsNamesOnly(t *testing.T) {
	e := newEditorEnv(t)
	smtp, ai := "smtp-sensitive-test-value", "ai-sensitive-test-value"
	configured, err := e.service.Update(e.ctx, UpdateSettingsInput{SmtpPassword: &smtp, ModerationAPIKey: &ai})
	if err != nil {
		t.Fatal(err)
	}
	smtpCipher := e.column(`SELECT smtp_password FROM site_settings WHERE id=1`)
	aiCipher := e.column(`SELECT moderation_api_key FROM site_settings WHERE id=1`)
	if smtpCipher == smtp || aiCipher == ai {
		t.Fatal("secret stored as plaintext")
	}
	if plain, err := crypto.Decrypt(editorFieldKey, smtpCipher); err != nil || plain != smtp {
		t.Fatalf("SMTP ciphertext cannot be decrypted: %v", err)
	}
	jsonWithoutSecrets(t, configured, smtp, ai, smtpCipher, aiCipher)
	empty := ""
	kept, err := e.service.Update(e.ctx, UpdateSettingsInput{SmtpPassword: &empty, ModerationAPIKey: &empty})
	if err != nil {
		t.Fatal(err)
	}
	if !kept.HasSmtpPassword || !kept.HasModerationAPIKey || e.column(`SELECT smtp_password FROM site_settings WHERE id=1`) != smtpCipher || e.column(`SELECT moderation_api_key FROM site_settings WHERE id=1`) != aiCipher {
		t.Fatal("empty explicit secret fields changed stored ciphertext")
	}
	clear := true
	cleared, err := e.service.Update(e.ctx, UpdateSettingsInput{ClearSmtpPassword: &clear, ClearModerationAPIKey: &clear})
	if err != nil {
		t.Fatal(err)
	}
	if cleared.HasSmtpPassword || cleared.HasModerationAPIKey || e.column(`SELECT smtp_password FROM site_settings WHERE id=1`) != "" || e.column(`SELECT moderation_api_key FROM site_settings WHERE id=1`) != "" {
		t.Fatal("explicit clear failed")
	}
	rows, err := e.d.ReadPool().Query(`SELECT data FROM audit_log WHERE object_type='site_settings'`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	seen := false
	for rows.Next() {
		var raw string
		if err := rows.Scan(&raw); err != nil {
			t.Fatal(err)
		}
		if strings.Contains(raw, smtp) || strings.Contains(raw, ai) || strings.Contains(raw, smtpCipher) || strings.Contains(raw, aiCipher) {
			t.Fatal("audit recorded secret value")
		}
		if strings.Contains(raw, "smtp_password") {
			seen = true
		}
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	if !seen {
		t.Fatal("audit did not retain changed field names")
	}
}
func TestEditorAutosaveCannotCarrySecretFields(t *testing.T) {
	e := newEditorEnv(t)
	response := e.request(http.MethodPatch, "/api/admin/settings", `{"base_version":1,"changes":{"smtp_password":"forbidden-inline-secret"}}`, e.ctx.Viewer)
	if response.Code != 400 {
		t.Fatalf("autosave accepted secret field: %d %s", response.Code, response.Body.String())
	}
	if e.column(`SELECT smtp_password FROM site_settings WHERE id=1`) != "" {
		t.Fatal("unknown secret field persisted")
	}
}

func TestBackupEnableRequiresCompleteSavedCredentialsAndKeepsSiblings(t *testing.T) {
	e := newEditorEnv(t)
	page, _, err := e.service.getBackupWith(e.ctx.Context, e.d.ReadPool())
	if err != nil {
		t.Fatal(err)
	}
	enabled := true
	retention := 30
	partial, err := e.service.patchBackup(e.ctx, BackupPatchIn{BaseVersion: page.Version, Changes: BackupChanges{Enabled: &enabled, RetentionDays: &retention}})
	if err != nil {
		t.Fatal(err)
	}
	if partial.Values.Enabled || partial.Values.RetentionDays != 30 || len(partial.Fields["enabled"]) == 0 || len(partial.Saved) != 1 {
		t.Fatalf("qualification receipt=%+v", partial)
	}
	secret, err := e.module.backupSecret(e.ctx, BackupSecretIn{SecretAccessKey: "s3-private-test-key"})
	if err != nil {
		t.Fatal(err)
	}
	endpoint, region, bucket, prefix, key := "https://storage.example.test", "auto", "club-bucket", "daily/", "access-test-key"
	configured, err := e.service.patchBackup(e.ctx, BackupPatchIn{BaseVersion: secret.Version, Changes: BackupChanges{Endpoint: &endpoint, Region: &region, Bucket: &bucket, Prefix: &prefix, AccessKeyID: &key, Enabled: &enabled}})
	if err != nil {
		t.Fatal(err)
	}
	if !configured.Values.Enabled || configured.Values.Bucket != bucket || !configured.Values.HasSecretAccessKey {
		t.Fatal("complete saved settings could not enable backup")
	}
	config, isEnabled, days, err := e.service.StorageConfig(e.ctx.Context)
	if err != nil {
		t.Fatal(err)
	}
	if !isEnabled || days != 30 || config.SecretAccessKey != "s3-private-test-key" {
		t.Fatal("internal storage boundary did not decrypt actual secret")
	}
	jsonWithoutSecrets(t, configured, "s3-private-test-key", e.column(`SELECT secret_access_key FROM backup_settings WHERE id=1`))
}
func TestBackupConflictCurrentAndInvalidFieldsDoNotExposeSecret(t *testing.T) {
	e := newEditorEnv(t)
	secret, err := e.module.backupSecret(e.ctx, BackupSecretIn{SecretAccessKey: "s3-private-test-key"})
	if err != nil {
		t.Fatal(err)
	}
	bucket := "new-bucket"
	_, err = e.service.patchBackup(e.ctx, BackupPatchIn{BaseVersion: secret.Version - 1, Changes: BackupChanges{Bucket: &bucket}})
	assertEditorStatus(t, err, 409)
	var failure *api.Error
	if !errors.As(err, &failure) || failure.Current == nil {
		t.Fatal("backup conflict omitted current")
	}
	jsonWithoutSecrets(t, failure.Current, "s3-private-test-key", e.column(`SELECT secret_access_key FROM backup_settings WHERE id=1`))
	badEndpoint := "https://user:pass@storage.example.test/path?token=secret"
	retention := 0
	prefix := "../escape"
	rejected, err := e.service.patchBackup(e.ctx, BackupPatchIn{BaseVersion: secret.Version, Changes: BackupChanges{Endpoint: &badEndpoint, RetentionDays: &retention, Prefix: &prefix}})
	if err != nil {
		t.Fatal(err)
	}
	if rejected.Version != secret.Version || len(rejected.Saved) != 0 || len(rejected.Fields["endpoint"]) == 0 || len(rejected.Fields["prefix"]) == 0 || len(rejected.Fields["retention_days"]) == 0 {
		t.Fatalf("invalid backup patch=%+v", rejected)
	}
	if e.column(`SELECT bucket FROM backup_settings WHERE id=1`) == bucket {
		t.Fatal("stale bucket committed")
	}
}
func TestBackupSecretDedicatedPOSTPreservesBlankClearsAndNeverEchoes(t *testing.T) {
	e := newEditorEnv(t)
	first, err := e.module.backupSecret(e.ctx, BackupSecretIn{SecretAccessKey: "s3-private-test-key"})
	if err != nil {
		t.Fatal(err)
	}
	ciphertext := e.column(`SELECT secret_access_key FROM backup_settings WHERE id=1`)
	if ciphertext == "" || ciphertext == "s3-private-test-key" {
		t.Fatal("S3 secret not encrypted")
	}
	jsonWithoutSecrets(t, first, "s3-private-test-key", ciphertext)
	kept, err := e.module.backupSecret(e.ctx, BackupSecretIn{})
	if err != nil {
		t.Fatal(err)
	}
	if kept.Version != first.Version || !kept.HasSecretAccessKey || e.column(`SELECT secret_access_key FROM backup_settings WHERE id=1`) != ciphertext {
		t.Fatal("blank secret action changed saved secret")
	}
	e.exec(`UPDATE backup_settings SET enabled=1 WHERE id=1`)
	cleared, err := e.module.backupSecret(e.ctx, BackupSecretIn{Clear: true})
	if err != nil {
		t.Fatal(err)
	}
	if cleared.HasSecretAccessKey || cleared.Version != first.Version+1 || e.column(`SELECT secret_access_key FROM backup_settings WHERE id=1`) != "" {
		t.Fatal("explicit backup clear failed")
	}
	var enabled bool
	if err := e.d.ReadPool().QueryRow(`SELECT enabled FROM backup_settings WHERE id=1`).Scan(&enabled); err != nil {
		t.Fatal(err)
	}
	if enabled {
		t.Fatal("clearing secret left incomplete backup enabled")
	}
	audit := e.column(`SELECT data FROM audit_log WHERE action='backup_settings.secret' ORDER BY id DESC LIMIT 1`)
	if strings.Contains(audit, "s3-private-test-key") || strings.Contains(audit, ciphertext) || !strings.Contains(audit, "cleared") {
		t.Fatalf("secret audit invalid=%s", audit)
	}
	get := e.request(http.MethodGet, "/api/admin/settings/backup/secret", "", e.ctx.Viewer)
	if get.Code != 405 && get.Code != 404 {
		t.Fatalf("secret GET=%d", get.Code)
	}
	bad := e.request(http.MethodPatch, "/api/admin/settings/backup", `{"base_version":1,"changes":{"secret_access_key":"no-inline-secret"}}`, e.ctx.Viewer)
	if bad.Code != 400 {
		t.Fatalf("backup autosave accepted secret: %d %s", bad.Code, bad.Body.String())
	}
}
func TestSettingsAndBackupRoutesRejectVisitorsDisabledAndNonSuperusers(t *testing.T) {
	e := newEditorEnv(t)
	registry := &api.Registry{}
	e.module.Routes(registry)
	for _, route := range registry.Routes() {
		for _, viewer := range []*app.Viewer{nil, {ID: 1, Superuser: true, Disabled: true}, {ID: 1}} {
			response := e.request(route.Method, route.Pattern, `{}`, viewer)
			want := 403
			if viewer == nil || viewer.Disabled {
				want = 401
			}
			if response.Code != want {
				t.Fatalf("%s %s=%d want=%d body=%s", route.Method, route.Pattern, response.Code, want, response.Body.String())
			}
		}
	}
}
func TestLegacyEncryptedSettingsAndBackupCredentialsRemainByteIdentical(t *testing.T) {
	e := newEditorEnv(t)
	legacy, err := sql.Open("sqlite", filepath.Join(t.TempDir(), "legacy.sqlite"))
	if err != nil {
		t.Fatal(err)
	}
	defer legacy.Close()
	_, err = legacy.Exec(`CREATE TABLE core_sitesettings(id INTEGER PRIMARY KEY,site_description TEXT,from_name TEXT,email_subject_prefix TEXT,smtp_host TEXT,smtp_port INTEGER,smtp_security TEXT,smtp_username TEXT,smtp_password TEXT,from_address TEXT,founded_on TEXT,default_share_image_id INTEGER,qq_group_url TEXT,team_max_members INTEGER,team_max_captained INTEGER,tournament_reminder_hours INTEGER,scrim_reminder_hours INTEGER,moderation_api_key TEXT,backup_s3_enabled INTEGER,backup_s3_endpoint TEXT,backup_s3_region TEXT,backup_s3_bucket TEXT,backup_s3_prefix TEXT,backup_s3_access_key_id TEXT,backup_s3_secret_access_key TEXT)`)
	if err != nil {
		t.Fatal(err)
	}
	smtp, err := crypto.Encrypt(editorFieldKey, "old-smtp-test-secret")
	if err != nil {
		t.Fatal(err)
	}
	ai, err := crypto.Encrypt(editorFieldKey, "old-ai-test-secret")
	if err != nil {
		t.Fatal(err)
	}
	backup, err := crypto.Encrypt(editorFieldKey, "old-s3-test-secret")
	if err != nil {
		t.Fatal(err)
	}
	_, err = legacy.Exec(`INSERT INTO core_sitesettings VALUES(1,'旧站','社团','[社团]','smtp.example.test',465,'ssl','mailer',?,'site@example.test','2020-01-01',NULL,'https://example.test/group',10,3,24,2,?,1,'https://storage.example.test','auto','club','archive/','access-id',?)`, smtp, ai, backup)
	if err != nil {
		t.Fatal(err)
	}
	if err := ImportLegacySettings(e.ctx.Context, e.d, legacy); err != nil {
		t.Fatal(err)
	}
	if err := ImportLegacyBackupSettings(e.ctx.Context, e.d, legacy); err != nil {
		t.Fatal(err)
	}
	if e.column(`SELECT smtp_password FROM site_settings WHERE id=1`) != smtp || e.column(`SELECT moderation_api_key FROM site_settings WHERE id=1`) != ai || e.column(`SELECT secret_access_key FROM backup_settings WHERE id=1`) != backup {
		t.Fatal("legacy import rewrote credential ciphertext")
	}
	config, enabled, _, err := e.service.StorageConfig(e.ctx.Context)
	if err != nil {
		t.Fatal(err)
	}
	if !enabled || config.SecretAccessKey != "old-s3-test-secret" {
		t.Fatal("imported encrypted storage credential cannot be used internally")
	}
	dto, err := e.service.Get(e.ctx.Context)
	if err != nil {
		t.Fatal(err)
	}
	page, _, err := e.service.getBackupWith(e.ctx.Context, e.d.ReadPool())
	if err != nil {
		t.Fatal(err)
	}
	jsonWithoutSecrets(t, []any{dto, page}, smtp, ai, backup, "old-smtp-test-secret", "old-ai-test-secret", "old-s3-test-secret")
	var unchanged string
	if err := legacy.QueryRow(`SELECT backup_s3_secret_access_key FROM core_sitesettings WHERE id=1`).Scan(&unchanged); err != nil {
		t.Fatal(err)
	}
	if unchanged != backup {
		t.Fatal("import wrote the old database")
	}
}
