-- 00011 战队与成员展示（12 号文档 7、规则 R083–R108、R236–R237）。
-- site_settings：全站设置（M5 先放战队的两个上限，后面的里程碑往上加列）。
-- teams / team_memberships / team_applications / team_alumni：战队四张表，字段照搬现行站。
-- member_groups / member_group_memberships：成员展示页的分组两张表。

-- +goose Up
CREATE TABLE site_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    team_max_members INTEGER NOT NULL DEFAULT 10,
    team_max_captained INTEGER NOT NULL DEFAULT 3,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
) STRICT;

INSERT INTO site_settings (id, team_max_members, team_max_captained, version, updated_at)
VALUES (1, 10, 3, 1, '2026-10-09T00:00:00.000000Z');

-- 队标放在自己的图片集合里，删换队标时只清这个集合里的（规则 106、219）。
INSERT INTO image_collections (id, name, key, created_at)
VALUES (5, '队标', 'team_logo', '2026-10-09T00:00:00.000000Z')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    logo_image_id INTEGER REFERENCES images(id) ON DELETE SET NULL,
    is_recruiting INTEGER NOT NULL DEFAULT 1,
    recruiting_roles TEXT NOT NULL DEFAULT '',
    member_contact TEXT NOT NULL DEFAULT '',
    disbanded_at TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
) STRICT;

-- 队名在未解散的战队里不分大小写唯一（规则 83，并发时的兜底）。
CREATE UNIQUE INDEX teams_active_name ON teams (lower(name)) WHERE disbanded_at IS NULL;
CREATE INDEX teams_created ON teams (created_at);

CREATE TABLE team_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('captain', 'member')),
    joined_at TEXT NOT NULL,
    UNIQUE (team_id, user_id)
) STRICT;

-- 每队至多一个队长。
CREATE UNIQUE INDEX team_memberships_one_captain ON team_memberships (team_id) WHERE role = 'captain';
CREATE INDEX team_memberships_user ON team_memberships (user_id);

CREATE TABLE team_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    applicant_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_tank INTEGER NOT NULL DEFAULT 0,
    role_damage INTEGER NOT NULL DEFAULT 0,
    role_support INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    decided_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    decided_at TEXT,
    decision_note TEXT NOT NULL DEFAULT '',
    captain_reminded_at TEXT,
    created_at TEXT NOT NULL
) STRICT;

-- 同一个人对同一支队同时只能有一条待审申请（规则 88）。
CREATE UNIQUE INDEX team_applications_one_pending ON team_applications (team_id, applicant_id)
    WHERE status = 'pending';
CREATE INDEX team_applications_applicant ON team_applications (applicant_id);
CREATE INDEX team_applications_pending_age ON team_applications (status, created_at);

CREATE TABLE team_alumni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('captain', 'member')),
    joined_at TEXT NOT NULL,
    left_at TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (reason IN ('left', 'removed')),
    UNIQUE (team_id, user_id)
) STRICT;

CREATE INDEX team_alumni_user ON team_alumni (user_id);

CREATE TABLE member_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    is_visible INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
) STRICT;

-- 非空的组名不分大小写唯一；空名是还没填完的新组，不受限。
CREATE UNIQUE INDEX member_groups_name ON member_groups (lower(name)) WHERE name <> '';

CREATE TABLE member_group_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES member_groups(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE (group_id, user_id)
) STRICT;

CREATE INDEX member_group_memberships_user ON member_group_memberships (user_id);

-- +goose Down
DROP TABLE member_group_memberships;
DROP TABLE member_groups;
DROP TABLE team_alumni;
DROP TABLE team_applications;
DROP TABLE team_memberships;
DROP TABLE teams;
DELETE FROM image_collections WHERE key = 'team_logo';
DROP TABLE site_settings;
