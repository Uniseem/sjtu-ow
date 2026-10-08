-- 00005 任务队列、worker 锁、定时器（12 号文档 5.10）。
-- 设计前提是只有一个 worker：锁行的心跳在 120 秒内，第二个起不来。

-- +goose Up
CREATE TABLE jobs (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL,
  args TEXT NOT NULL,
  lane TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 0,
  run_after TEXT NOT NULL,
  status TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT NOT NULL DEFAULT '',
  dedupe_key TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT
) STRICT;

CREATE INDEX jobs_claim ON jobs (lane, status, run_after);

CREATE TABLE worker_lock (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  owner TEXT NOT NULL,
  heartbeat_at TEXT NOT NULL
) STRICT;

CREATE TABLE worker_status (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  started_at TEXT NOT NULL,
  heartbeat_at TEXT NOT NULL
) STRICT;

CREATE TABLE schedule_runs (
  name TEXT PRIMARY KEY,
  last_run_at TEXT NOT NULL
) STRICT;

-- +goose Down
DROP TABLE schedule_runs;
DROP TABLE worker_status;
DROP TABLE worker_lock;
DROP TABLE jobs;
