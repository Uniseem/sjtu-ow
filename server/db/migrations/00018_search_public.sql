-- +goose Up
-- Wagtail 本页或祖先的访问限制：公开搜索只列不受限的文章。
-- 这是搜索可见标记，不改变文章的 live 发布状态。
ALTER TABLE pages ADD COLUMN search_public INTEGER NOT NULL DEFAULT 1 CHECK (search_public IN (0, 1));

-- +goose Down
ALTER TABLE pages DROP COLUMN search_public;
