-- 00016 全站设置补充列、用户头像与头像审核（12 号文档 5.11/5.13、规则 R221、设计 14.1）。

-- +goose Up
ALTER TABLE users ADD COLUMN avatar_image_id INTEGER REFERENCES images(id) ON DELETE SET NULL;

CREATE TABLE avatar_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    image_id INTEGER REFERENCES images(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'approved' CHECK (status IN ('pending', 'approved', 'rejected', 'withdrawn', 'taken_down')),
    handling_note TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT,
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX avatar_submissions_user ON avatar_submissions (user_id, created_at);
CREATE INDEX avatar_submissions_status ON avatar_submissions (status, created_at);

ALTER TABLE site_settings ADD COLUMN site_description TEXT NOT NULL DEFAULT '';
ALTER TABLE site_settings ADD COLUMN from_name TEXT NOT NULL DEFAULT 'SJTU-OW';
ALTER TABLE site_settings ADD COLUMN email_subject_prefix TEXT NOT NULL DEFAULT '[SJTU-OW]';
ALTER TABLE site_settings ADD COLUMN smtp_host TEXT NOT NULL DEFAULT '';
ALTER TABLE site_settings ADD COLUMN smtp_port INTEGER NOT NULL DEFAULT 465;
ALTER TABLE site_settings ADD COLUMN smtp_security TEXT NOT NULL DEFAULT 'ssl';
ALTER TABLE site_settings ADD COLUMN smtp_username TEXT NOT NULL DEFAULT '';
ALTER TABLE site_settings ADD COLUMN smtp_password TEXT NOT NULL DEFAULT '';
ALTER TABLE site_settings ADD COLUMN from_address TEXT NOT NULL DEFAULT '';
ALTER TABLE site_settings ADD COLUMN founded_on TEXT NOT NULL DEFAULT '';
ALTER TABLE site_settings ADD COLUMN default_share_image_id INTEGER REFERENCES images(id) ON DELETE SET NULL;
ALTER TABLE site_settings ADD COLUMN hero_image_id INTEGER REFERENCES images(id) ON DELETE SET NULL;
ALTER TABLE site_settings ADD COLUMN banner_news_id INTEGER REFERENCES images(id) ON DELETE SET NULL;
ALTER TABLE site_settings ADD COLUMN banner_tournaments_id INTEGER REFERENCES images(id) ON DELETE SET NULL;
ALTER TABLE site_settings ADD COLUMN banner_scrims_id INTEGER REFERENCES images(id) ON DELETE SET NULL;
ALTER TABLE site_settings ADD COLUMN banner_teams_id INTEGER REFERENCES images(id) ON DELETE SET NULL;
ALTER TABLE site_settings ADD COLUMN banner_members_id INTEGER REFERENCES images(id) ON DELETE SET NULL;
ALTER TABLE site_settings ADD COLUMN moderation_provider TEXT NOT NULL DEFAULT '';
ALTER TABLE site_settings ADD COLUMN moderation_api_key TEXT NOT NULL DEFAULT '';
ALTER TABLE site_settings ADD COLUMN moderation_base_url TEXT NOT NULL DEFAULT '';
ALTER TABLE site_settings ADD COLUMN moderation_model TEXT NOT NULL DEFAULT '';
ALTER TABLE site_settings ADD COLUMN moderation_max_tokens INTEGER NOT NULL DEFAULT 2000;
ALTER TABLE site_settings ADD COLUMN moderation_timeout_seconds INTEGER NOT NULL DEFAULT 60;
ALTER TABLE site_settings ADD COLUMN moderation_extra_params TEXT NOT NULL DEFAULT '{}';
ALTER TABLE site_settings ADD COLUMN moderation_daily_limit INTEGER NOT NULL DEFAULT 0;
ALTER TABLE site_settings ADD COLUMN moderation_notify_email TEXT NOT NULL DEFAULT '';

-- +goose Down
DROP TABLE avatar_submissions;
ALTER TABLE users DROP COLUMN avatar_image_id;
ALTER TABLE site_settings DROP COLUMN moderation_notify_email;
ALTER TABLE site_settings DROP COLUMN moderation_daily_limit;
ALTER TABLE site_settings DROP COLUMN moderation_extra_params;
ALTER TABLE site_settings DROP COLUMN moderation_timeout_seconds;
ALTER TABLE site_settings DROP COLUMN moderation_max_tokens;
ALTER TABLE site_settings DROP COLUMN moderation_model;
ALTER TABLE site_settings DROP COLUMN moderation_base_url;
ALTER TABLE site_settings DROP COLUMN moderation_api_key;
ALTER TABLE site_settings DROP COLUMN moderation_provider;
ALTER TABLE site_settings DROP COLUMN banner_members_id;
ALTER TABLE site_settings DROP COLUMN banner_teams_id;
ALTER TABLE site_settings DROP COLUMN banner_scrims_id;
ALTER TABLE site_settings DROP COLUMN banner_tournaments_id;
ALTER TABLE site_settings DROP COLUMN banner_news_id;
ALTER TABLE site_settings DROP COLUMN hero_image_id;
ALTER TABLE site_settings DROP COLUMN default_share_image_id;
ALTER TABLE site_settings DROP COLUMN founded_on;
ALTER TABLE site_settings DROP COLUMN from_address;
ALTER TABLE site_settings DROP COLUMN smtp_password;
ALTER TABLE site_settings DROP COLUMN smtp_username;
ALTER TABLE site_settings DROP COLUMN smtp_security;
ALTER TABLE site_settings DROP COLUMN smtp_port;
ALTER TABLE site_settings DROP COLUMN smtp_host;
ALTER TABLE site_settings DROP COLUMN email_subject_prefix;
ALTER TABLE site_settings DROP COLUMN from_name;
ALTER TABLE site_settings DROP COLUMN site_description;
