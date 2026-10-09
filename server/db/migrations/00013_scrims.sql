-- 00013 内战（12 号文档 7、规则 R144–R170）。
-- scrims：内战活动（board_version 给分队页做乐观并发）；scrim_signups：报名和分队结果。
-- site_settings 补社团 QQ 群链接（提醒信里写，规则 151）。

-- +goose Up
ALTER TABLE site_settings ADD COLUMN qq_group_url TEXT NOT NULL DEFAULT '';

CREATE TABLE scrims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    description_plain TEXT NOT NULL DEFAULT '',
    starts_at TEXT,
    signup_closes_at TEXT,
    format TEXT NOT NULL DEFAULT 'rq_5v5' CHECK (format IN ('rq_5v5', 'rq_6v6', 'open_5v5', 'open_6v6')),
    sjtu_only INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'finished', 'cancelled')),
    teams_generated_at TEXT,
    roster_changed_at TEXT,
    reminder_sent_at TEXT,
    moved_from TEXT,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    version INTEGER NOT NULL DEFAULT 1,
    board_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
) STRICT;

CREATE INDEX scrims_status_starts ON scrims (status, starts_at);

CREATE TABLE scrim_signups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scrim_id INTEGER NOT NULL REFERENCES scrims(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_account_id INTEGER REFERENCES game_accounts(id) ON DELETE SET NULL,
    role_tank INTEGER NOT NULL DEFAULT 0,
    role_damage INTEGER NOT NULL DEFAULT 0,
    role_support INTEGER NOT NULL DEFAULT 0,
    is_selected INTEGER NOT NULL DEFAULT 0,
    team TEXT NOT NULL DEFAULT '' CHECK (team IN ('', 'a', 'b')),
    assigned_role TEXT NOT NULL DEFAULT '' CHECK (assigned_role IN ('', 'tank', 'damage', 'support')),
    rating_used INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (scrim_id, user_id),
    CHECK (role_tank = 1 OR role_damage = 1 OR role_support = 1)
) STRICT;

CREATE INDEX scrim_signups_user ON scrim_signups (user_id);

-- +goose Down
DROP TABLE scrim_signups;
DROP TABLE scrims;
ALTER TABLE site_settings DROP COLUMN qq_group_url;
