-- 00006 待发信（12 号文档 5.11、设计 10.5）。一次操作的信共用一个 batch。
-- state：waiting 等着、sent 发了、skipped 没发。7 天不再问，30 天由清理删掉。

-- +goose Up
CREATE TABLE held_letters (
  id INTEGER PRIMARY KEY,
  batch TEXT NOT NULL,
  actor_id INTEGER NOT NULL,
  letter TEXT NOT NULL,
  recipients TEXT NOT NULL,
  back TEXT NOT NULL DEFAULT '',
  in_back_office INTEGER NOT NULL DEFAULT 0,
  state TEXT NOT NULL DEFAULT 'waiting',
  created_at TEXT NOT NULL,
  decided_at TEXT NOT NULL DEFAULT ''
) STRICT;

CREATE INDEX held_letters_batch ON held_letters (batch, state);
CREATE INDEX held_letters_actor ON held_letters (actor_id, state, created_at);

-- +goose Down
DROP TABLE held_letters;
