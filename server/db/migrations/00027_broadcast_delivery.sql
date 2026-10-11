-- +goose Up
-- Root integrates into the next migration after the baseline broadcasts table.
-- This marker records an atomic enqueue to the outbox, not SMTP delivery.
ALTER TABLE broadcasts ADD COLUMN delivered_at TEXT;

-- +goose Down
ALTER TABLE broadcasts DROP COLUMN delivered_at;
