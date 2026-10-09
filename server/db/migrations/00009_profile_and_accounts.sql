-- 00009 账号域资料、游戏 ID、联系方式与扩展（12 号文档 7、5.7、5.8、规则 16–21）。
-- users: 增加 main_role、flex_roles 字段。
-- game_accounts: 游戏 ID 表（上限 5 个，battletag_norm 全局唯一，段位分数，更新时间）。
-- contacts: 联系方式表（每种类型每人限 1 条）。

-- +goose Up
ALTER TABLE users ADD COLUMN main_role TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN flex_roles TEXT NOT NULL DEFAULT '';

CREATE TABLE game_accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  battletag TEXT NOT NULL,
  battletag_norm TEXT NOT NULL UNIQUE,
  rank_tank INTEGER,
  rank_damage INTEGER,
  rank_support INTEGER,
  ranks_updated_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
) STRICT;

CREATE INDEX game_accounts_user ON game_accounts (user_id);
CREATE INDEX game_accounts_battletag_norm ON game_accounts (battletag_norm);

CREATE TABLE contacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  value TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (user_id, type)
) STRICT;

CREATE INDEX contacts_user ON contacts (user_id);

-- +goose Down
DROP TABLE contacts;
DROP TABLE game_accounts;
-- SQLite 3.35.0+ 支持 DROP COLUMN
ALTER TABLE users DROP COLUMN flex_roles;
ALTER TABLE users DROP COLUMN main_role;
