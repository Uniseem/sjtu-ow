-- +goose Up
-- Game-account data is read by the split generator outside its write
-- transaction. Only changes to actual board inputs invalidate its version.
-- +goose StatementBegin
CREATE TRIGGER scrim_board_game_update AFTER UPDATE ON game_accounts
WHEN OLD.battletag IS NOT NEW.battletag
  OR OLD.rank_tank IS NOT NEW.rank_tank
  OR OLD.rank_damage IS NOT NEW.rank_damage
  OR OLD.rank_support IS NOT NEW.rank_support
  OR OLD.user_id IS NOT NEW.user_id
BEGIN
  UPDATE scrims SET board_version = board_version + 1,
    roster_changed_at = CASE WHEN teams_generated_at IS NOT NULL
      THEN CASE WHEN julianday('now') > julianday(teams_generated_at)
        THEN strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        ELSE strftime('%Y-%m-%dT%H:%M:%fZ', teams_generated_at, '+0.001 seconds') END
      ELSE roster_changed_at END
  WHERE id IN (SELECT scrim_id FROM scrim_signups
    WHERE game_account_id = NEW.id AND user_id IN (OLD.user_id, NEW.user_id));
END;
-- +goose StatementEnd

-- Capture the affected boards before ON DELETE SET NULL loses the reference.
-- +goose StatementBegin
CREATE TRIGGER scrim_board_game_delete BEFORE DELETE ON game_accounts
BEGIN
  UPDATE scrims SET board_version = board_version + 1,
    roster_changed_at = CASE WHEN teams_generated_at IS NOT NULL
      THEN CASE WHEN julianday('now') > julianday(teams_generated_at)
        THEN strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        ELSE strftime('%Y-%m-%dT%H:%M:%fZ', teams_generated_at, '+0.001 seconds') END
      ELSE roster_changed_at END
  WHERE id IN (SELECT scrim_id FROM scrim_signups
    WHERE game_account_id = OLD.id AND user_id = OLD.user_id);
END;
-- +goose StatementEnd

-- +goose Down
DROP TRIGGER scrim_board_game_delete;
DROP TRIGGER scrim_board_game_update;
