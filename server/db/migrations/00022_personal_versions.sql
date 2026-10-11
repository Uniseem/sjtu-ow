-- +goose Up
-- Existing identities remain intact. Object versions start at one; old
-- whole-form requests still work but must advance the same conflict counter.
ALTER TABLE game_accounts ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE contacts ADD COLUMN version INTEGER NOT NULL DEFAULT 1;

-- +goose Down
ALTER TABLE contacts DROP COLUMN version;
ALTER TABLE game_accounts DROP COLUMN version;
