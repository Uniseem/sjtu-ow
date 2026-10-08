-- 00004 会话（12 号文档 5.7）。令牌是 32 字节随机数，库里只存它的 SHA-256。
-- 割接时不搬 Django 的会话，全员重新登录。过期行由定时器轮清理。

-- +goose Up
CREATE TABLE sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  reauth_at TEXT NOT NULL DEFAULT '',
  last_seen_at TEXT NOT NULL
) STRICT;

CREATE INDEX sessions_user ON sessions (user_id);
CREATE INDEX sessions_expires ON sessions (expires_at);

-- +goose Down
DROP TABLE sessions;
