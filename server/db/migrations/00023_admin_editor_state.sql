-- +goose Up
ALTER TABLE feature_user_rules ADD COLUMN note TEXT NOT NULL DEFAULT '';
ALTER TABLE feature_role_restrictions ADD COLUMN note TEXT NOT NULL DEFAULT '';
ALTER TABLE image_collections ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
CREATE TABLE content_editor_drafts (
 scope TEXT PRIMARY KEY,
 version INTEGER NOT NULL DEFAULT 1 CHECK(version > 0),
 content TEXT NOT NULL DEFAULT '{}',
 live_content TEXT NOT NULL DEFAULT '{}',
 updated_at TEXT NOT NULL,
 author_id INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- +goose Down
DROP TABLE content_editor_drafts;
ALTER TABLE image_collections DROP COLUMN version;
ALTER TABLE feature_role_restrictions DROP COLUMN note;
ALTER TABLE feature_user_rules DROP COLUMN note;
