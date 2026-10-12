-- +goose Up
ALTER TABLE users ADD COLUMN last_login_at TEXT;

-- +goose Down
ALTER TABLE users DROP COLUMN last_login_at;
