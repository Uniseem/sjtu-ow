-- +goose Up
ALTER TABLE avatar_submissions ADD COLUMN note TEXT NOT NULL DEFAULT '';
UPDATE avatar_submissions SET note=handling_note;
ALTER TABLE avatar_submissions ADD COLUMN reason TEXT NOT NULL DEFAULT '';
ALTER TABLE avatar_submissions ADD COLUMN reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL;

-- +goose Down
ALTER TABLE avatar_submissions DROP COLUMN reviewed_by;
ALTER TABLE avatar_submissions DROP COLUMN reason;
ALTER TABLE avatar_submissions DROP COLUMN note;
