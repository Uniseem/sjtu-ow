-- +goose Up
-- Root integrates this into the next numbered database migration.
-- Triggers protect cross-domain mutations as well as the tournament writers.
ALTER TABLE tournaments ADD COLUMN pool_version INTEGER NOT NULL DEFAULT 1;

-- +goose StatementBegin
CREATE TRIGGER tournament_pool_signup_insert AFTER INSERT ON individual_signups
BEGIN
  UPDATE tournaments SET pool_version = pool_version + 1 WHERE id = NEW.tournament_id;
END;
-- +goose StatementEnd
-- +goose StatementBegin
CREATE TRIGGER tournament_pool_signup_update AFTER UPDATE ON individual_signups
BEGIN
  UPDATE tournaments SET pool_version = pool_version + 1 WHERE id IN (OLD.tournament_id, NEW.tournament_id);
END;
-- +goose StatementEnd
-- +goose StatementBegin
CREATE TRIGGER tournament_pool_signup_delete AFTER DELETE ON individual_signups
BEGIN
  UPDATE tournaments SET pool_version = pool_version + 1 WHERE id = OLD.tournament_id;
END;
-- +goose StatementEnd

-- +goose StatementBegin
CREATE TRIGGER tournament_pool_registration_insert AFTER INSERT ON registrations
BEGIN
  UPDATE tournaments SET pool_version = pool_version + 1 WHERE id = NEW.tournament_id;
END;
-- +goose StatementEnd
-- +goose StatementBegin
CREATE TRIGGER tournament_pool_registration_update AFTER UPDATE ON registrations
BEGIN
  UPDATE tournaments SET pool_version = pool_version + 1 WHERE id IN (OLD.tournament_id, NEW.tournament_id);
END;
-- +goose StatementEnd
-- +goose StatementBegin
CREATE TRIGGER tournament_pool_registration_delete AFTER DELETE ON registrations
BEGIN
  UPDATE tournaments SET pool_version = pool_version + 1 WHERE id = OLD.tournament_id;
END;
-- +goose StatementEnd

-- +goose StatementBegin
CREATE TRIGGER tournament_pool_member_insert AFTER INSERT ON registration_members
BEGIN
  UPDATE tournaments SET pool_version = pool_version + 1 WHERE id = NEW.tournament_id;
END;
-- +goose StatementEnd
-- +goose StatementBegin
CREATE TRIGGER tournament_pool_member_update AFTER UPDATE ON registration_members
BEGIN
  UPDATE tournaments SET pool_version = pool_version + 1 WHERE id IN (OLD.tournament_id, NEW.tournament_id);
END;
-- +goose StatementEnd
-- +goose StatementBegin
CREATE TRIGGER tournament_pool_member_delete AFTER DELETE ON registration_members
BEGIN
  UPDATE tournaments SET pool_version = pool_version + 1 WHERE id = OLD.tournament_id;
END;
-- +goose StatementEnd

-- A deleted/edited game ID or account deactivation may make a previously
-- valid board illegal even when the individual signup row itself is unchanged.
-- +goose StatementBegin
CREATE TRIGGER tournament_pool_game_update AFTER UPDATE ON game_accounts
WHEN OLD.battletag IS NOT NEW.battletag
  OR OLD.rank_tank IS NOT NEW.rank_tank
  OR OLD.rank_damage IS NOT NEW.rank_damage
  OR OLD.rank_support IS NOT NEW.rank_support
BEGIN
  UPDATE tournaments SET pool_version = pool_version + 1
  WHERE id IN (SELECT tournament_id FROM individual_signups WHERE game_account_id = NEW.id);
END;
-- +goose StatementEnd
-- +goose StatementBegin
CREATE TRIGGER tournament_pool_game_delete BEFORE DELETE ON game_accounts
BEGIN
  UPDATE tournaments SET pool_version = pool_version + 1
  WHERE id IN (SELECT tournament_id FROM individual_signups WHERE game_account_id = OLD.id);
END;
-- +goose StatementEnd
-- +goose StatementBegin
CREATE TRIGGER tournament_pool_user_update AFTER UPDATE ON users
WHEN OLD.is_active IS NOT NEW.is_active OR OLD.is_sjtu IS NOT NEW.is_sjtu
BEGIN
  UPDATE tournaments SET pool_version = pool_version + 1 WHERE id IN (
    SELECT tournament_id FROM individual_signups WHERE user_id = NEW.id
    UNION SELECT tournament_id FROM registration_members WHERE user_id = NEW.id
  );
END;
-- +goose StatementEnd

-- Changed roster constraints must invalidate an already loaded compilation.
-- +goose StatementBegin
CREATE TRIGGER tournament_pool_rules_update AFTER UPDATE ON tournaments
WHEN OLD.roster_min IS NOT NEW.roster_min OR OLD.roster_max IS NOT NEW.roster_max
  OR OLD.sjtu_only IS NOT NEW.sjtu_only OR OLD.registration_mode IS NOT NEW.registration_mode
  OR OLD.status IS NOT NEW.status
BEGIN
  UPDATE tournaments SET pool_version = pool_version + 1 WHERE id = NEW.id;
END;
-- +goose StatementEnd

-- +goose Down
DROP TRIGGER tournament_pool_rules_update;
DROP TRIGGER tournament_pool_user_update;
DROP TRIGGER tournament_pool_game_delete;
DROP TRIGGER tournament_pool_game_update;
DROP TRIGGER tournament_pool_member_delete;
DROP TRIGGER tournament_pool_member_update;
DROP TRIGGER tournament_pool_member_insert;
DROP TRIGGER tournament_pool_registration_delete;
DROP TRIGGER tournament_pool_registration_update;
DROP TRIGGER tournament_pool_registration_insert;
DROP TRIGGER tournament_pool_signup_delete;
DROP TRIGGER tournament_pool_signup_update;
DROP TRIGGER tournament_pool_signup_insert;
ALTER TABLE tournaments DROP COLUMN pool_version;
