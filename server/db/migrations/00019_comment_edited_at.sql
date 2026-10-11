-- +goose Up
-- 作者编辑时间独立于管理更新时间；已有 Go 数据不能用 updated_at 猜测编辑历史。
ALTER TABLE comments ADD COLUMN edited_at TEXT;

-- +goose Down
ALTER TABLE comments DROP COLUMN edited_at;
