-- +goose Up
-- Anonymous browser workflow state exists for every submitted valid address,
-- including unknown/disabled/previously verified accounts. It grants no login.
CREATE TABLE account_code_flows (
  token_hash TEXT PRIMARY KEY,
  purpose TEXT NOT NULL CHECK (purpose IN ('signup','password_reset')),
  email_norm TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  closed INTEGER NOT NULL DEFAULT 0 CHECK (closed IN (0,1))
) STRICT;
CREATE INDEX account_code_flows_expiry ON account_code_flows(expires_at);

-- +goose Down
DROP TABLE account_code_flows;
