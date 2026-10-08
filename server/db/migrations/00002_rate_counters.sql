-- 00002 限流计数（12 号文档 5.9）。key 是「u:编号」或「ip:地址」，bucket 是
-- 「限流名|时间片」。worker 每天删过期的桶（定时器轮做，表先立起来）。

-- +goose Up
CREATE TABLE rate_counters (
  key TEXT NOT NULL,
  bucket TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (key, bucket)
) STRICT;

-- +goose Down
DROP TABLE rate_counters;
