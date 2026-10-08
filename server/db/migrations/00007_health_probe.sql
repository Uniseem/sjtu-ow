-- 00007 /healthz 的写探测（12 号文档 5.15）。写入后立刻回滚，表里不留行。

-- +goose Up
CREATE TABLE health_probe (
  id INTEGER PRIMARY KEY,
  token TEXT NOT NULL
) STRICT;

-- +goose Down
DROP TABLE health_probe;
