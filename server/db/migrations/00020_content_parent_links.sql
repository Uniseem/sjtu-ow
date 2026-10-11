-- +goose Up
-- Wagtail 栏目关系：父页面可能是未迁入的 Home/root，保留原编号而不做 FK 重映射。
ALTER TABLE pages ADD COLUMN parent_id INTEGER;
CREATE INDEX idx_pages_parent_published ON pages(parent_id, first_published_at);
-- 图片集合全部迁入，默认图库含所有子目录。
ALTER TABLE image_collections ADD COLUMN parent_id INTEGER REFERENCES image_collections(id) ON DELETE SET NULL;
CREATE INDEX idx_image_collections_parent ON image_collections(parent_id);

-- +goose Down
DROP INDEX idx_image_collections_parent;
ALTER TABLE image_collections DROP COLUMN parent_id;
DROP INDEX idx_pages_parent_published;
ALTER TABLE pages DROP COLUMN parent_id;
