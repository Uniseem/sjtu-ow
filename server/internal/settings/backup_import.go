package settings

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// ImportLegacyBackupSettings keeps the existing encrypted credential bytes.
// No secret is printed or decrypted by migration; the configured field key
// remains responsible for interpreting the same Fernet format at runtime.
func ImportLegacyBackupSettings(ctx context.Context, d *db.DB, legacy *sql.DB) error {
	var exists int
	if err := legacy.QueryRowContext(ctx, `SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='core_sitesettings'`).Scan(&exists); err != nil {
		return err
	}
	if exists == 0 {
		return nil
	}
	columns := map[string]bool{}
	rows, err := legacy.QueryContext(ctx, `PRAGMA table_info(core_sitesettings)`)
	if err != nil {
		return err
	}
	for rows.Next() {
		var cid, notNull, primary int
		var name, kind string
		var fallback any
		if err := rows.Scan(&cid, &name, &kind, &notNull, &fallback, &primary); err != nil {
			rows.Close()
			return err
		}
		columns[name] = true
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	if !columns["backup_s3_enabled"] {
		return nil
	}
	fields := []struct{ name, fallback string }{
		{"backup_s3_enabled", "0"}, {"backup_s3_endpoint", "''"}, {"backup_s3_region", "'auto'"}, {"backup_s3_bucket", "''"},
		{"backup_s3_prefix", "'sjtu-ow/'"}, {"backup_s3_access_key_id", "''"}, {"backup_s3_secret_access_key", "''"},
	}
	selectColumns := []string{}
	for _, field := range fields {
		if columns[field.name] {
			selectColumns = append(selectColumns, "COALESCE("+field.name+","+field.fallback+")")
		} else {
			selectColumns = append(selectColumns, field.fallback)
		}
	}
	var enabled int
	var endpoint, region, bucket, prefix, key, secret string
	err = legacy.QueryRowContext(ctx, `SELECT `+strings.Join(selectColumns, ",")+` FROM core_sitesettings ORDER BY id LIMIT 1`).Scan(&enabled, &endpoint, &region, &bucket, &prefix, &key, &secret)
	if err == sql.ErrNoRows {
		return nil
	}
	if err != nil {
		return fmt.Errorf("读取旧异地备份设置失败：%w", err)
	}
	return d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(txCtx, `INSERT INTO backup_settings(id,version,enabled,endpoint,region,bucket,prefix,access_key_id,secret_access_key,retention_days,updated_at)
   VALUES(1,1,?,?,?,?,?,?,?,14,?) ON CONFLICT(id) DO UPDATE SET
   version=backup_settings.version+1,enabled=excluded.enabled,endpoint=excluded.endpoint,region=excluded.region,bucket=excluded.bucket,prefix=excluded.prefix,
   access_key_id=excluded.access_key_id,secret_access_key=excluded.secret_access_key,updated_at=excluded.updated_at`, enabled, endpoint, region, bucket, prefix, key, secret, db.FormatUTC(time.Now().UTC()))
		return err
	})
}
