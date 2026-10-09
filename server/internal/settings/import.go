package settings

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// ImportLegacySettings 从现行 Django SQLite 库导入全站设置数据。
func ImportLegacySettings(ctx context.Context, d *db.DB, legacy *sql.DB) error {
	var hasTable bool
	_ = legacy.QueryRowContext(ctx, `SELECT 1 FROM sqlite_master WHERE type='table' AND name='core_sitesettings'`).Scan(&hasTable)
	if !hasTable {
		return nil
	}

	setCols := make(map[string]bool)
	{
		sRows, err := legacy.QueryContext(ctx, `PRAGMA table_info(core_sitesettings)`)
		if err == nil {
			defer sRows.Close()
			for sRows.Next() {
				var cid, notnull, pk int
				var name, ctype string
				var dflt any
				if err := sRows.Scan(&cid, &name, &ctype, &notnull, &dflt, &pk); err == nil {
					setCols[name] = true
				}
			}
		}
	}
	colHero := "NULL AS hero_image_id"
	if setCols["hero_image_id"] {
		colHero = "hero_image_id"
	}
	colBNews := "NULL AS banner_news_id"
	if setCols["banner_news_id"] {
		colBNews = "banner_news_id"
	}
	colBTourn := "NULL AS banner_tournaments_id"
	if setCols["banner_tournaments_id"] {
		colBTourn = "banner_tournaments_id"
	}
	colBScrim := "NULL AS banner_scrims_id"
	if setCols["banner_scrims_id"] {
		colBScrim = "banner_scrims_id"
	}
	colBTeams := "NULL AS banner_teams_id"
	if setCols["banner_teams_id"] {
		colBTeams = "banner_teams_id"
	}
	colBMemb := "NULL AS banner_members_id"
	if setCols["banner_members_id"] {
		colBMemb = "banner_members_id"
	}
	colModEnabled := "0 AS moderation_enabled"
	if setCols["moderation_enabled"] {
		colModEnabled = "moderation_enabled"
	}
	colModKey := "NULL AS moderation_api_key"
	if setCols["moderation_api_key"] {
		colModKey = "moderation_api_key"
	}
	colModBaseURL := "NULL AS moderation_base_url"
	if setCols["moderation_base_url"] {
		colModBaseURL = "moderation_base_url"
	}
	colModModel := "NULL AS moderation_model"
	if setCols["moderation_model"] {
		colModModel = "moderation_model"
	}
	colModLimit := "0 AS moderation_daily_limit"
	if setCols["moderation_daily_limit"] {
		colModLimit = "moderation_daily_limit"
	}
	colModAlert := "NULL AS moderation_alert_email"
	if setCols["moderation_alert_email"] {
		colModAlert = "moderation_alert_email"
	}

	row := legacy.QueryRowContext(ctx, fmt.Sprintf(`SELECT
		site_description, from_name, email_subject_prefix,
		smtp_host, smtp_port, smtp_security, smtp_username, smtp_password, from_address,
		founded_on, default_share_image_id, %s,
		%s, %s, %s, %s, %s,
		qq_group_url, team_max_members, team_max_captained, tournament_reminder_hours, scrim_reminder_hours,
		%s, %s, %s, %s,
		%s, %s
		FROM core_sitesettings LIMIT 1`,
		colHero, colBNews, colBTourn, colBScrim, colBTeams, colBMemb,
		colModEnabled, colModKey, colModBaseURL, colModModel,
		colModLimit, colModAlert))

	var siteDesc, fromName, prefix string
	var smtpHost, smtpSecurity, smtpUser, smtpPass, fromAddr string
	var smtpPort, teamMaxMembers, teamMaxCaptained, tournRemind, scrimRemind, modDailyLimit int
	var foundedOn, qqURL, modKey, modBaseURL, modModel, modAlertEmail sql.NullString
	var defShare, hero, bNews, bTourn, bScrim, bTeams, bMemb sql.NullInt64
	var modEnabled int

	err := row.Scan(
		&siteDesc, &fromName, &prefix,
		&smtpHost, &smtpPort, &smtpSecurity, &smtpUser, &smtpPass, &fromAddr,
		&foundedOn, &defShare, &hero,
		&bNews, &bTourn, &bScrim, &bTeams, &bMemb,
		&qqURL, &teamMaxMembers, &teamMaxCaptained, &tournRemind, &scrimRemind,
		&modEnabled, &modKey, &modBaseURL, &modModel,
		&modDailyLimit, &modAlertEmail,
	)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil
		}
		return fmt.Errorf("读取旧库 core_sitesettings 失败: %w", err)
	}

	return d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		nowStr := db.FormatUTC(time.Now().UTC())
		var defShareVal, heroVal, bNewsVal, bTournVal, bScrimVal, bTeamsVal, bMembVal any
		if defShare.Valid {
			defShareVal = defShare.Int64
		}
		if hero.Valid {
			heroVal = hero.Int64
		}
		if bNews.Valid {
			bNewsVal = bNews.Int64
		}
		if bTourn.Valid {
			bTournVal = bTourn.Int64
		}
		if bScrim.Valid {
			bScrimVal = bScrim.Int64
		}
		if bTeams.Valid {
			bTeamsVal = bTeams.Int64
		}
		if bMemb.Valid {
			bMembVal = bMemb.Int64
		}

		configured := 0
		if modKey.Valid && modKey.String != "" {
			configured = 1
		}

		_, err := tx.ExecContext(txCtx, `UPDATE site_settings SET
			site_description = ?,
			from_name = ?,
			email_subject_prefix = ?,
			smtp_host = ?,
			smtp_port = ?,
			smtp_security = ?,
			smtp_username = ?,
			smtp_password = ?,
			from_address = ?,
			founded_on = ?,
			default_share_image_id = ?,
			hero_image_id = ?,
			banner_news_id = ?,
			banner_tournaments_id = ?,
			banner_scrims_id = ?,
			banner_teams_id = ?,
			banner_members_id = ?,
			qq_group_url = ?,
			team_max_members = ?,
			team_max_captained = ?,
			tournament_reminder_hours = ?,
			scrim_reminder_hours = ?,
			moderation_enabled = ?,
			moderation_configured = ?,
			moderation_provider = 'deepseek',
			moderation_api_key = ?,
			moderation_base_url = ?,
			moderation_model = ?,
			moderation_daily_limit = ?,
			moderation_notify_email = ?,
			updated_at = ?
		WHERE id = 1`,
			siteDesc, fromName, prefix,
			smtpHost, smtpPort, smtpSecurity, smtpUser, smtpPass, fromAddr,
			foundedOn.String, defShareVal, heroVal,
			bNewsVal, bTournVal, bScrimVal, bTeamsVal, bMembVal,
			qqURL.String, teamMaxMembers, teamMaxCaptained, tournRemind, scrimRemind,
			modEnabled, configured, modKey.String,
			modBaseURL.String, modModel.String, modDailyLimit, modAlertEmail.String,
			nowStr,
		)
		return err
	})
}
