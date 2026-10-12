-- +goose Up
ALTER TABLE site_settings ADD COLUMN max_game_accounts INTEGER NOT NULL DEFAULT 5 CHECK(max_game_accounts BETWEEN 0 AND 2147483647);
ALTER TABLE site_settings ADD COLUMN moderation_image_enabled INTEGER NOT NULL DEFAULT 0 CHECK(moderation_image_enabled IN (0,1));
-- +goose Down
ALTER TABLE site_settings DROP COLUMN moderation_image_enabled;
ALTER TABLE site_settings DROP COLUMN max_game_accounts;
