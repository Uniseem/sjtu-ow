-- +goose Up
CREATE TABLE backup_settings (
 id INTEGER PRIMARY KEY CHECK(id=1),
 version INTEGER NOT NULL DEFAULT 1,
 enabled INTEGER NOT NULL DEFAULT 0,
 endpoint TEXT NOT NULL DEFAULT '',
 region TEXT NOT NULL DEFAULT 'auto',
 bucket TEXT NOT NULL DEFAULT '',
 prefix TEXT NOT NULL DEFAULT 'sjtu-ow/',
 access_key_id TEXT NOT NULL DEFAULT '',
 secret_access_key TEXT NOT NULL DEFAULT '',
 retention_days INTEGER NOT NULL DEFAULT 14,
 updated_at TEXT NOT NULL
);
INSERT INTO backup_settings(id,updated_at) VALUES(1,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
-- +goose Down
DROP TABLE backup_settings;
