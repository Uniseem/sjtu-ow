-- 00008 账号域基础表（12 号文档 7、5.7、5.8、规则 1–15）。
-- users: 账号基础信息与标志（去掉了 username/first_name/last_name/is_staff）。
-- user_roles: 只存 4 个管理角色；交大/校外/投稿者为派生角色。
-- feature_role_restrictions: 角色级功能限制。
-- feature_user_rules: 单用户功能规则（denied=1 为禁止，denied=0 为单独放行）。
-- email_codes: 邮箱验证码（只存 SHA-256 哈希）。
-- email_changes: 换绑邮箱的中间状态。

-- +goose Up
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL,
  email_norm TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  nickname TEXT NOT NULL,
  is_sjtu INTEGER NOT NULL DEFAULT 0,
  agreed_terms_at TEXT NOT NULL,
  agreed_cross_border_at TEXT NOT NULL,
  email_verified_at TEXT,
  password_changed_at TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  is_active INTEGER NOT NULL DEFAULT 1,
  is_superuser INTEGER NOT NULL DEFAULT 0,
  deactivation_note TEXT NOT NULL DEFAULT '',
  motto TEXT NOT NULL DEFAULT '',
  show_rank INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
) STRICT;

CREATE INDEX users_email_norm ON users (email_norm);
CREATE INDEX users_is_active ON users (is_active);

CREATE TABLE user_roles (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (user_id, role)
) STRICT;

CREATE INDEX user_roles_user ON user_roles (user_id);

CREATE TABLE feature_role_restrictions (
  role TEXT NOT NULL,
  feature TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (role, feature)
) STRICT;

CREATE TABLE feature_user_rules (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  feature TEXT NOT NULL,
  denied INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (user_id, feature)
) STRICT;

CREATE INDEX feature_user_rules_user ON feature_user_rules (user_id);

CREATE TABLE email_codes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  purpose TEXT NOT NULL,
  email_norm TEXT NOT NULL,
  code_hash TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
) STRICT;

CREATE INDEX email_codes_lookup ON email_codes (purpose, email_norm);

CREATE TABLE email_changes (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  new_email TEXT NOT NULL,
  new_email_norm TEXT NOT NULL,
  code_hash TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
) STRICT;

-- +goose Down
DROP TABLE email_changes;
DROP TABLE email_codes;
DROP TABLE feature_user_rules;
DROP TABLE feature_role_restrictions;
DROP TABLE user_roles;
DROP TABLE users;
