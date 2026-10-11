package settings

import (
	"context"
	"fmt"
	"net/url"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/crypto"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/storage"
)

type BackupValues struct {
	Enabled            bool   `json:"enabled"`
	Endpoint           string `json:"endpoint"`
	Region             string `json:"region"`
	Bucket             string `json:"bucket"`
	Prefix             string `json:"prefix"`
	AccessKeyID        string `json:"access_key_id"`
	HasSecretAccessKey bool   `json:"has_secret_access_key"`
	RetentionDays      int    `json:"retention_days"`
}
type BackupPage struct {
	Version int64        `json:"version"`
	Values  BackupValues `json:"values"`
}
type BackupChanges struct {
	Enabled       *bool   `json:"enabled,omitempty"`
	Endpoint      *string `json:"endpoint,omitempty"`
	Region        *string `json:"region,omitempty"`
	Bucket        *string `json:"bucket,omitempty"`
	Prefix        *string `json:"prefix,omitempty"`
	AccessKeyID   *string `json:"access_key_id,omitempty"`
	RetentionDays *int    `json:"retention_days,omitempty"`
}
type BackupPatchIn struct {
	BaseVersion int64         `json:"base_version"`
	Changes     BackupChanges `json:"changes"`
}
type BackupReceipt struct {
	Version int64               `json:"version"`
	Values  BackupValues        `json:"values"`
	Saved   []string            `json:"saved"`
	Fields  map[string][]string `json:"fields,omitempty"`
	SavedAt time.Time           `json:"saved_at"`
}
type BackupSecretIn struct {
	SecretAccessKey string `json:"secret_access_key"`
	Clear           bool   `json:"clear"`
}
type BackupSecretOut struct {
	HasSecretAccessKey bool   `json:"has_secret_access_key"`
	Version            int64  `json:"version"`
	Message            string `json:"message"`
}

func (s *Service) getBackupWith(ctx context.Context, q db.DBTX) (*BackupPage, string, error) {
	var page BackupPage
	var secret string
	err := q.QueryRowContext(ctx, `SELECT version,enabled,endpoint,region,bucket,prefix,access_key_id,secret_access_key,retention_days FROM backup_settings WHERE id=1`).Scan(&page.Version, &page.Values.Enabled, &page.Values.Endpoint, &page.Values.Region, &page.Values.Bucket, &page.Values.Prefix, &page.Values.AccessKeyID, &secret, &page.Values.RetentionDays)
	if err != nil {
		return nil, "", err
	}
	page.Values.HasSecretAccessKey = secret != ""
	return &page, secret, nil
}
func (m *Module) getBackup(ctx *app.Ctx, _ struct{}) (*BackupPage, error) {
	page, _, err := m.svc.getBackupWith(ctx.Context, m.svc.d.ReadPool())
	return page, err
}
func (m *Module) patchBackup(ctx *app.Ctx, in BackupPatchIn) (*BackupReceipt, error) {
	return m.svc.patchBackup(ctx, in)
}
func (s *Service) patchBackup(ctx *app.Ctx, in BackupPatchIn) (*BackupReceipt, error) {
	if ctx.Viewer == nil || ctx.Viewer.Disabled || !ctx.Viewer.Superuser {
		return nil, api.Forbidden()
	}
	if in.BaseVersion < 1 {
		return nil, api.Invalid("保存版本无效。")
	}
	now := ctx.Now().UTC()
	receipt := &BackupReceipt{Saved: []string{}, Fields: map[string][]string{}, SavedAt: now}
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		current, _, err := s.getBackupWith(txCtx, tx)
		if err != nil {
			return err
		}
		if current.Version != in.BaseVersion {
			return api.Stale(current)
		}
		values := current.Values
		sets := []string{}
		args := []any{}
		set := func(field string, value any) {
			sets = append(sets, field+"=?")
			args = append(args, value)
			receipt.Saved = append(receipt.Saved, field)
		}
		reject := func(field, message string) { receipt.Fields[field] = []string{message} }
		text := func(field string, value *string, max int, target *string) {
			if value == nil {
				return
			}
			normalized := strings.TrimSpace(*value)
			if utf8.RuneCountInString(normalized) > max || strings.ContainsAny(normalized, "\x00\r\n") {
				reject(field, fmt.Sprintf("最多 %d 个字符，不能包含换行。", max))
				return
			}
			*target = normalized
			set(field, normalized)
		}
		if in.Changes.Endpoint != nil {
			endpoint := strings.TrimSpace(*in.Changes.Endpoint)
			address, err := url.Parse(endpoint)
			if endpoint != "" && (err != nil || address.Scheme != "https" || address.Hostname() == "" || address.User != nil || address.RawQuery != "" || address.Fragment != "" || address.Path != "" && address.Path != "/") {
				reject("endpoint", "请填写不带路径、参数的 HTTPS 对象存储地址。")
			} else {
				values.Endpoint = endpoint
				set("endpoint", endpoint)
			}
		}
		text("region", in.Changes.Region, 32, &values.Region)
		text("bucket", in.Changes.Bucket, 64, &values.Bucket)
		text("access_key_id", in.Changes.AccessKeyID, 128, &values.AccessKeyID)
		if in.Changes.Prefix != nil {
			prefix, err := storage.NormalizePrefix(*in.Changes.Prefix)
			if err != nil {
				reject("prefix", err.Error())
			} else {
				values.Prefix = prefix
				set("prefix", prefix)
			}
		}
		if in.Changes.RetentionDays != nil {
			if *in.Changes.RetentionDays < 1 || *in.Changes.RetentionDays > 365 {
				reject("retention_days", "保留天数必须在 1 到 365 之间。")
			} else {
				values.RetentionDays = *in.Changes.RetentionDays
				set("retention_days", values.RetentionDays)
			}
		}
		if in.Changes.Enabled != nil {
			enabled := *in.Changes.Enabled
			if enabled && (values.Endpoint == "" || values.Bucket == "" || values.AccessKeyID == "" || !values.HasSecretAccessKey) {
				reject("enabled", "请先保存地址、存储桶和访问密钥，再开启异地备份。")
			} else {
				values.Enabled = enabled
				set("enabled", enabled)
			}
		}
		if len(sets) > 0 {
			sets = append(sets, "version=version+1", "updated_at=?")
			args = append(args, db.FormatUTC(now))
			if _, err := tx.ExecContext(txCtx, `UPDATE backup_settings SET `+strings.Join(sets, ",")+` WHERE id=1`, args...); err != nil {
				return err
			}
			if err := audit.Record(txCtx, tx, ctx.Viewer.ID, "backup_settings.update", "backup_settings", 1, map[string]any{"fields": receipt.Saved}, now); err != nil {
				return err
			}
		}
		latest, _, err := s.getBackupWith(txCtx, tx)
		if err != nil {
			return err
		}
		receipt.Version = latest.Version
		receipt.Values = latest.Values
		return nil
	})
	if err != nil {
		return nil, err
	}
	if len(receipt.Fields) == 0 {
		receipt.Fields = nil
	}
	return receipt, nil
}
func (m *Module) backupSecret(ctx *app.Ctx, in BackupSecretIn) (*BackupSecretOut, error) {
	if ctx.Viewer == nil || ctx.Viewer.Disabled || !ctx.Viewer.Superuser {
		return nil, api.Forbidden()
	}
	if len(in.SecretAccessKey) > 4096 || strings.ContainsAny(in.SecretAccessKey, "\r\n\x00") {
		return nil, api.InvalidFields(map[string][]string{"secret_access_key": {"密钥格式无效。"}})
	}
	var result BackupSecretOut
	err := m.svc.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		page, current, err := m.svc.getBackupWith(txCtx, tx)
		if err != nil {
			return err
		}
		secret := current
		if in.Clear {
			secret = ""
		} else if in.SecretAccessKey != "" {
			secret, err = crypto.Encrypt(m.svc.fieldKey, in.SecretAccessKey)
			if err != nil {
				return fmt.Errorf("加密备份密钥失败：%w", err)
			}
		}
		if secret != current {
			if _, err := tx.ExecContext(txCtx, `UPDATE backup_settings SET secret_access_key=?,version=version+1,enabled=CASE WHEN ?='' THEN 0 ELSE enabled END,updated_at=? WHERE id=1`, secret, secret, db.FormatUTC(ctx.Now().UTC())); err != nil {
				return err
			}
			if err := audit.Record(txCtx, tx, ctx.Viewer.ID, "backup_settings.secret", "backup_settings", 1, map[string]bool{"cleared": in.Clear, "set": !in.Clear && in.SecretAccessKey != ""}, ctx.Now().UTC()); err != nil {
				return err
			}
			page.Version++
		}
		result = BackupSecretOut{HasSecretAccessKey: secret != "", Version: page.Version, Message: "访问密钥已保存。"}
		return nil
	})
	return &result, err
}

// StorageConfig is an internal worker/CLI boundary. It is never an API output.
func (s *Service) StorageConfig(ctx context.Context) (storage.Config, bool, int, error) {
	page, encrypted, err := s.getBackupWith(ctx, s.d.ReadPool())
	if err != nil {
		return storage.Config{}, false, 0, err
	}
	secret := ""
	if encrypted != "" {
		secret, err = crypto.Decrypt(s.fieldKey, encrypted)
		if err != nil {
			return storage.Config{}, false, 0, fmt.Errorf("无法解密对象存储密钥")
		}
	}
	return storage.Config{Endpoint: page.Values.Endpoint, Region: page.Values.Region, Bucket: page.Values.Bucket, Prefix: page.Values.Prefix, AccessKeyID: page.Values.AccessKeyID, SecretAccessKey: secret}, page.Values.Enabled, page.Values.RetentionDays, nil
}
func (m *Module) testStorage(ctx *app.Ctx, _ struct{}) (TestEmailOut, error) {
	config, _, _, err := m.svc.StorageConfig(ctx.Context)
	if err != nil {
		return TestEmailOut{}, err
	}
	client, err := storage.New(config, nil)
	if err != nil {
		return TestEmailOut{}, api.Invalid(err.Error())
	}
	deadline, cancel := context.WithTimeout(ctx.Context, 60*time.Second)
	defer cancel()
	if err := client.Probe(deadline); err != nil {
		return TestEmailOut{}, api.Invalid(err.Error())
	}
	return TestEmailOut{Result: "ok", Message: "对象存储测试成功：已写入、读取并删除测试文件。"}, nil
}
func (m *Module) backupRoutes(r *api.Registry) {
	nav := api.Nav("settings", "site")
	api.Get(r, "/api/admin/settings/backup", api.Superuser, m.getBackup, nav)
	api.Patch(r, "/api/admin/settings/backup", api.Superuser, m.patchBackup, nav, api.NoLimit("超管版本化自动保存"))
	api.Post(r, "/api/admin/settings/backup/secret", api.Superuser, m.backupSecret, nav, api.NoLimit("超管显式只写密钥"))
	api.Post(r, "/api/admin/settings/test-storage", api.Superuser, m.testStorage, nav, api.NoLimit("超管测试保存的对象存储设置"))
}
