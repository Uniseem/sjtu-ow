-- 12 号文档 6.4：跨整页跳转的提示留在会话里，读取一次即消费。
-- +goose Up
ALTER TABLE sessions ADD COLUMN flash_message TEXT NOT NULL DEFAULT '';

-- +goose Down
ALTER TABLE sessions DROP COLUMN flash_message;
