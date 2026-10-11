-- +goose Up
-- 独立访问可见性；搜索可见性保留原语义，不能反过来用于授权。
ALTER TABLE pages ADD COLUMN is_public INTEGER NOT NULL DEFAULT 1 CHECK (is_public IN (0,1));
-- 既有 Go 缓存来自 Wagtail 本页/祖先限制，升级保留限制而非重新公开。
UPDATE pages SET is_public=search_public;

-- +goose Down
ALTER TABLE pages DROP COLUMN is_public;
