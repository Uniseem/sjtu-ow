-- 00012 赛事与报名（12 号文档 7、规则 R109–R143）。
-- tournaments：赛事；registrations：一支队的一次报名（team_id 为空表示临时队伍）；
-- registration_members：名单快照；registration_status_logs：只追加的状态日志；
-- individual_signups：个人报名（散人池）。
-- site_settings 补开赛提醒提前的小时数（赛事默认 24，内战默认 2，规则 138、151）。

-- +goose Up
ALTER TABLE site_settings ADD COLUMN tournament_reminder_hours INTEGER NOT NULL DEFAULT 24;
ALTER TABLE site_settings ADD COLUMN scrim_reminder_hours INTEGER NOT NULL DEFAULT 2;

CREATE TABLE tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    description_plain TEXT NOT NULL DEFAULT '',
    cover_image_id INTEGER REFERENCES images(id) ON DELETE SET NULL,
    starts_at TEXT,
    registration_opens_at TEXT,
    registration_closes_at TEXT,
    roster_min INTEGER NOT NULL DEFAULT 5,
    roster_max INTEGER NOT NULL DEFAULT 6,
    sjtu_only INTEGER NOT NULL DEFAULT 0,
    registration_mode TEXT NOT NULL DEFAULT 'individual' CHECK (registration_mode IN ('individual', 'team')),
    auto_approve INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'finished', 'cancelled')),
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    published_at TEXT,
    reminder_sent_at TEXT,
    moved_from TEXT,
    participant_contact TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (roster_min >= 1 AND roster_max <= 20 AND roster_min <= roster_max),
    CHECK (registration_opens_at IS NULL OR registration_closes_at IS NULL OR registration_opens_at < registration_closes_at)
) STRICT;

CREATE INDEX tournaments_status ON tournaments (status, registration_closes_at);

CREATE TABLE registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    team_id INTEGER REFERENCES teams(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'withdrawn')),
    team_name TEXT NOT NULL CHECK (team_name <> ''),
    roster_version INTEGER NOT NULL DEFAULT 1,
    submitted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    submitted_at TEXT NOT NULL,
    status_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (tournament_id, team_id)
) STRICT;

CREATE INDEX registrations_tournament_status ON registrations (tournament_id, status);
CREATE INDEX registrations_team ON registrations (team_id);

CREATE TABLE registration_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registration_id INTEGER NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    game_account_id INTEGER REFERENCES game_accounts(id) ON DELETE SET NULL,
    nickname TEXT NOT NULL,
    battletag TEXT NOT NULL,
    is_sjtu INTEGER NOT NULL DEFAULT 0,
    rank_tank INTEGER,
    rank_damage INTEGER,
    rank_support INTEGER,
    is_captain INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1
) STRICT;

-- 一人同一赛事只能在一个活跃名单上（规则 117）。
CREATE UNIQUE INDEX registration_members_one_active ON registration_members (tournament_id, user_id) WHERE is_active = 1;
CREATE INDEX registration_members_registration ON registration_members (registration_id);
CREATE INDEX registration_members_user ON registration_members (user_id);

CREATE TABLE registration_status_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registration_id INTEGER NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    from_status TEXT NOT NULL DEFAULT '',
    to_status TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    roster_version INTEGER NOT NULL DEFAULT 1,
    roster_snapshot TEXT,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX registration_status_logs_registration ON registration_status_logs (registration_id, id);

CREATE TABLE individual_signups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_account_id INTEGER REFERENCES game_accounts(id) ON DELETE SET NULL,
    role_tank INTEGER NOT NULL DEFAULT 0,
    role_damage INTEGER NOT NULL DEFAULT 0,
    role_support INTEGER NOT NULL DEFAULT 0,
    registration_id INTEGER REFERENCES registrations(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (tournament_id, user_id),
    CHECK (role_tank = 1 OR role_damage = 1 OR role_support = 1)
) STRICT;

CREATE INDEX individual_signups_user ON individual_signups (user_id);
CREATE INDEX individual_signups_registration ON individual_signups (registration_id);

-- +goose Down
DROP TABLE individual_signups;
DROP TABLE registration_status_logs;
DROP TABLE registration_members;
DROP TABLE registrations;
DROP TABLE tournaments;
ALTER TABLE site_settings DROP COLUMN scrim_reminder_hours;
ALTER TABLE site_settings DROP COLUMN tournament_reminder_hours;
