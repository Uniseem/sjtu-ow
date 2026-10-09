-- 00014 内容审核记录与统一的操作记录（12 号文档 7、规则 R184–R205）。
-- moderation_items：待复核记录（AI 巡查按 D5 割接后再做，这里先有表、送审接口、人工复核）；
-- audit_log：操作记录，统一一张（操作人、动作、对象类型、对象编号、数据、时间，设计 15.5）；
-- site_settings 加 AI 审核的两个开关。

-- +goose Up
ALTER TABLE site_settings ADD COLUMN moderation_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE site_settings ADD COLUMN moderation_configured INTEGER NOT NULL DEFAULT 0;

CREATE TABLE moderation_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL DEFAULT 0,
    field TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    excerpt TEXT NOT NULL,
    full_text TEXT NOT NULL DEFAULT '',
    text_hash TEXT NOT NULL,
    risk TEXT NOT NULL DEFAULT 'unknown' CHECK (risk IN ('none', 'low', 'medium', 'high', 'unknown')),
    categories TEXT NOT NULL DEFAULT '[]',
    reason TEXT NOT NULL DEFAULT '',
    quote TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'ok', 'handled', 'ignored')),
    reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TEXT,
    handling_note TEXT NOT NULL DEFAULT '',
    checked_at TEXT,
    notified_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    failed_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (target_type, target_id, field, text_hash)
) STRICT;

CREATE INDEX moderation_items_queue ON moderation_items (status, risk, created_at);
CREATE INDEX moderation_items_hash ON moderation_items (text_hash);
CREATE INDEX moderation_items_author ON moderation_items (author_id);

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id INTEGER NOT NULL DEFAULT 0,
    data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX audit_log_object ON audit_log (object_type, object_id, id);
CREATE INDEX audit_log_actor ON audit_log (actor_id, created_at);

-- +goose Down
DROP TABLE audit_log;
DROP TABLE moderation_items;
ALTER TABLE site_settings DROP COLUMN moderation_configured;
ALTER TABLE site_settings DROP COLUMN moderation_enabled;
