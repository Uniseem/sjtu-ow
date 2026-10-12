-- +goose Up
-- Imports protect immutable font objects before writing them outside the DB lock.
CREATE TABLE font_blob_claims (
 path TEXT NOT NULL,
 hash TEXT NOT NULL,
 lease_token TEXT NOT NULL,
 expires_at TEXT NOT NULL,
 PRIMARY KEY(path,lease_token)
) STRICT;
CREATE INDEX font_blob_claims_expiry ON font_blob_claims(expires_at);

-- +goose Down
DROP TABLE font_blob_claims;
