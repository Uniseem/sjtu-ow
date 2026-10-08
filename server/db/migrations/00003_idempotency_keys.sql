-- 00003 幂等键回执（12 号文档 5.5、13 号 D 节）。同一个人同一个键 24 小时内
-- 重放直接回当时的回执；status=0 表示「认领了还在处理」（防双击）。
-- worker 定期清过期的行（定时器轮做）。

-- +goose Up
CREATE TABLE idempotency_keys (
  user_id INTEGER NOT NULL,
  key TEXT NOT NULL,
  method TEXT NOT NULL,
  path TEXT NOT NULL,
  status INTEGER NOT NULL DEFAULT 0,
  response TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  PRIMARY KEY (user_id, key)
) STRICT;

-- +goose Down
DROP TABLE idempotency_keys;
