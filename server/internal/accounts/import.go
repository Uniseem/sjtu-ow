package accounts

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// LegacyGroupRoleMap 映射现行 Django 用户组名称到新栈角色键（12 号文档 7、表 7.1）。
var LegacyGroupRoleMap = map[string]string{
	"内容编辑":  RoleContentEditor,
	"赛事管理员": RoleTournamentAdmin,
	"内战管理员": RoleScrimAdmin,
	"认证作者":  RoleCertifiedAuthor,
	"交大用户":  RoleSJTU,
	"校外用户":  RoleExternal,
	"投稿者":   RoleContributor,
}

func parseAndFormatUTC(s string, fallback time.Time) string {
	if s == "" {
		return db.FormatUTC(fallback)
	}
	t, err := db.ParseUTC(s)
	if err != nil {
		return db.FormatUTC(fallback)
	}
	return db.FormatUTC(t)
}

// ImportLegacyAccounts 从现行 Django SQLite 库导入账号域所有数据。
// legacy 必须是以只读模式打开的旧数据库连接。
func ImportLegacyAccounts(ctx context.Context, d *db.DB, legacy *sql.DB) error {
	now := time.Now().UTC()
	nowStr := db.FormatUTC(now)

	// 1. 读取旧库验证邮箱映射 (account_emailaddress)
	verifiedMap := make(map[int64]bool)
	{
		rows, err := legacy.QueryContext(ctx, `SELECT user_id, verified FROM account_emailaddress WHERE "primary" = 1`)
		if err == nil {
			defer rows.Close()
			for rows.Next() {
				var uid int64
				var verified int
				if err := rows.Scan(&uid, &verified); err == nil {
					verifiedMap[uid] = (verified == 1)
				}
			}
		}
	}

	// 2. 导入用户表 (accounts_user -> users)
	var hasAvatarCol bool
	{
		rows, err := legacy.QueryContext(ctx, `PRAGMA table_info(accounts_user)`)
		if err == nil {
			defer rows.Close()
			for rows.Next() {
				var cid, notnull, pk int
				var name, ctype string
				var dflt any
				if err := rows.Scan(&cid, &name, &ctype, &notnull, &dflt, &pk); err == nil {
					if name == "avatar_id" {
						hasAvatarCol = true
						break
					}
				}
			}
		}
	}
	avatarCol := "NULL AS avatar_id"
	if hasAvatarCol {
		avatarCol = "avatar_id"
	}
	query := fmt.Sprintf(`SELECT
		id, email, password, nickname, is_sjtu,
		agreed_terms_at, agreed_cross_border_at, date_joined,
		is_active, is_superuser, deactivation_note, motto,
		main_role, flex_roles, show_rank, accepts_announcements, calendar_version, %s
		FROM accounts_user ORDER BY id ASC`, avatarCol)
	userRows, err := legacy.QueryContext(ctx, query)
	if err != nil {
		return fmt.Errorf("读取旧库 accounts_user 失败: %w", err)
	}
	defer userRows.Close()

	err = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		for userRows.Next() {
			var id int64
			var email, password, nickname, deactivationNote, motto, mainRole, flexRoles string
			var isSJTU, isActive, isSuperuser, showRank, acceptsAnnouncements, calendarVersion int
			var agreedTerms, agreedCB, dateJoined string
			var avatarID sql.NullInt64

			if err := userRows.Scan(
				&id, &email, &password, &nickname, &isSJTU,
				&agreedTerms, &agreedCB, &dateJoined,
				&isActive, &isSuperuser, &deactivationNote, &motto,
				&mainRole, &flexRoles, &showRank, &acceptsAnnouncements, &calendarVersion, &avatarID,
			); err != nil {
				return fmt.Errorf("解析 accounts_user 行失败: %w", err)
			}

			emailNorm := NormalizeEmail(email)
			agreedTermsUTC := parseAndFormatUTC(agreedTerms, now)
			agreedCBUTC := parseAndFormatUTC(agreedCB, now)
			dateJoinedUTC := parseAndFormatUTC(dateJoined, now)

			var emailVerifiedStr any
			// 如果是超管或在 account_emailaddress 中已验证，置 email_verified_at
			if isSuperuser == 1 || verifiedMap[id] {
				emailVerifiedStr = dateJoinedUTC
			}

			var avatarVal any
			if avatarID.Valid {
				avatarVal = avatarID.Int64
			}

			_, err := tx.ExecContext(txCtx, `INSERT INTO users (
				id, email, email_norm, password_hash, nickname, is_sjtu,
				agreed_terms_at, agreed_cross_border_at, email_verified_at, password_changed_at,
				version, is_active, is_superuser, deactivation_note, motto, main_role, flex_roles, show_rank,
				accepts_announcements, calendar_version, avatar_image_id, created_at, updated_at
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
			ON CONFLICT (id) DO UPDATE SET
				email = excluded.email,
				email_norm = excluded.email_norm,
				password_hash = excluded.password_hash,
				nickname = excluded.nickname,
				is_sjtu = excluded.is_sjtu,
				agreed_terms_at = excluded.agreed_terms_at,
				agreed_cross_border_at = excluded.agreed_cross_border_at,
				email_verified_at = excluded.email_verified_at,
				is_active = excluded.is_active,
				is_superuser = excluded.is_superuser,
				deactivation_note = excluded.deactivation_note,
				motto = excluded.motto,
				main_role = excluded.main_role,
				flex_roles = excluded.flex_roles,
				show_rank = excluded.show_rank,
				accepts_announcements = excluded.accepts_announcements,
				calendar_version = excluded.calendar_version,
				avatar_image_id = excluded.avatar_image_id,
				updated_at = excluded.updated_at`,
				id, email, emailNorm, password, nickname, isSJTU,
				agreedTermsUTC, agreedCBUTC, emailVerifiedStr,
				isActive, isSuperuser, deactivationNote, motto, mainRole, flexRoles, showRank,
				acceptsAnnouncements, calendarVersion, avatarVal, dateJoinedUTC, dateJoinedUTC,
			)
			if err != nil {
				return fmt.Errorf("写入 users 用户 %d 失败: %w", id, err)
			}
		}
		return userRows.Err()
	})
	if err != nil {
		return err
	}

	// 3. 导入游戏 ID (accounts_gameaccount -> game_accounts)
	gaRows, err := legacy.QueryContext(ctx, `SELECT
		id, user_id, battletag, rank_tank, rank_damage, rank_support, ranks_updated_at
		FROM accounts_gameaccount ORDER BY id ASC`)
	if err == nil {
		defer gaRows.Close()
		err = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			for gaRows.Next() {
				var id, userID int64
				var battletag, ranksUpdatedAt string
				var tank, damage, support sql.NullInt64

				if err := gaRows.Scan(&id, &userID, &battletag, &tank, &damage, &support, &ranksUpdatedAt); err != nil {
					return err
				}

				norm := NormalizeBattletag(battletag)
				var tankVal, damageVal, supportVal any
				if tank.Valid {
					tankVal = tank.Int64
				}
				if damage.Valid {
					damageVal = damage.Int64
				}
				if support.Valid {
					supportVal = support.Int64
				}
				ranksUpdatedUTC := parseAndFormatUTC(ranksUpdatedAt, now)

				_, err := tx.ExecContext(txCtx, `INSERT INTO game_accounts (
					id, user_id, battletag, battletag_norm, rank_tank, rank_damage, rank_support,
					ranks_updated_at, created_at, updated_at
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				ON CONFLICT (id) DO UPDATE SET
					battletag = excluded.battletag,
					battletag_norm = excluded.battletag_norm,
					rank_tank = excluded.rank_tank,
					rank_damage = excluded.rank_damage,
					rank_support = excluded.rank_support,
					ranks_updated_at = excluded.ranks_updated_at`,
					id, userID, battletag, norm, tankVal, damageVal, supportVal,
					ranksUpdatedUTC, ranksUpdatedUTC, ranksUpdatedUTC,
				)
				if err != nil {
					return fmt.Errorf("写入 game_accounts %d 失败: %w", id, err)
				}
			}
			return gaRows.Err()
		})
		if err != nil {
			return err
		}
	}

	// 4. 导入联系方式 (accounts_contactmethod -> contacts)
	contactRows, err := legacy.QueryContext(ctx, `SELECT id, user_id, type, value FROM accounts_contactmethod ORDER BY id ASC`)
	if err == nil {
		defer contactRows.Close()
		err = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			for contactRows.Next() {
				var id, userID int64
				var cType, value string
				if err := contactRows.Scan(&id, &userID, &cType, &value); err != nil {
					return err
				}

				_, err := tx.ExecContext(txCtx, `INSERT INTO contacts (
					id, user_id, type, value, created_at, updated_at
				) VALUES (?, ?, ?, ?, ?, ?)
				ON CONFLICT (id) DO UPDATE SET
					type = excluded.type,
					value = excluded.value`,
					id, userID, cType, value, nowStr, nowStr,
				)
				if err != nil {
					return fmt.Errorf("写入 contacts %d 失败: %w", id, err)
				}
			}
			return contactRows.Err()
		})
		if err != nil {
			return err
		}
	}

	// 5. 导入用户角色 (auth_group + accounts_user_groups -> user_roles)
	roleRows, err := legacy.QueryContext(ctx, `SELECT ug.user_id, g.name
		FROM accounts_user_groups ug
		JOIN auth_group g ON ug.group_id = g.id`)
	if err == nil {
		defer roleRows.Close()
		err = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			for roleRows.Next() {
				var userID int64
				var groupName string
				if err := roleRows.Scan(&userID, &groupName); err != nil {
					return err
				}
				roleKey, ok := LegacyGroupRoleMap[groupName]
				if !ok {
					continue
				}
				// 仅四个管理角色存库（12 号文档 5.8）
				isStored := false
				for _, sr := range AllStoredRoles {
					if sr == roleKey {
						isStored = true
						break
					}
				}
				if !isStored {
					continue
				}

				_, err := tx.ExecContext(txCtx, `INSERT INTO user_roles (user_id, role, created_at)
					VALUES (?, ?, ?) ON CONFLICT DO NOTHING`,
					userID, roleKey, nowStr)
				if err != nil {
					return err
				}
			}
			return roleRows.Err()
		})
		if err != nil {
			return err
		}
	}

	// 6. 导入角色功能限制 (accounts_featuregrouprestriction -> feature_role_restrictions)
	restrRows, err := legacy.QueryContext(ctx, `SELECT g.name, r.feature
		FROM accounts_featuregrouprestriction r
		JOIN auth_group g ON r.group_id = g.id`)
	if err == nil {
		defer restrRows.Close()
		err = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			for restrRows.Next() {
				var groupName, feature string
				if err := restrRows.Scan(&groupName, &feature); err != nil {
					return err
				}
				roleKey, ok := LegacyGroupRoleMap[groupName]
				if !ok {
					continue
				}
				feat := app.Feature(strings.ToLower(strings.TrimSpace(feature)))
				if !IsValidFeature(feat) {
					continue
				}

				_, err := tx.ExecContext(txCtx, `INSERT INTO feature_role_restrictions (role, feature, created_at)
					VALUES (?, ?, ?) ON CONFLICT DO NOTHING`,
					roleKey, string(feat), nowStr)
				if err != nil {
					return err
				}
			}
			return restrRows.Err()
		})
		if err != nil {
			return err
		}
	}

	// 7. 导入单用户功能规则 (accounts_featureuserrule -> feature_user_rules)
	ruleRows, err := legacy.QueryContext(ctx, `SELECT user_id, feature, allowed FROM accounts_featureuserrule`)
	if err == nil {
		defer ruleRows.Close()
		err = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			for ruleRows.Next() {
				var userID int64
				var feature string
				var allowed int
				if err := ruleRows.Scan(&userID, &feature, &allowed); err != nil {
					return err
				}
				feat := app.Feature(strings.ToLower(strings.TrimSpace(feature)))
				if !IsValidFeature(feat) {
					continue
				}
				denied := 0
				if allowed == 0 {
					denied = 1
				}

				_, err := tx.ExecContext(txCtx, `INSERT INTO feature_user_rules (user_id, feature, denied, created_at)
					VALUES (?, ?, ?, ?) ON CONFLICT (user_id, feature) DO UPDATE SET denied = excluded.denied`,
					userID, string(feat), denied, nowStr)
				if err != nil {
					return err
				}
			}
			return ruleRows.Err()
		})
		if err != nil {
			return err
		}
	}

	// 8. 导入头像审核记录 (accounts_avatarsubmission -> avatar_submissions)
	var hasAvatarSub bool
	_ = legacy.QueryRowContext(ctx, `SELECT 1 FROM sqlite_master WHERE type='table' AND name='accounts_avatarsubmission'`).Scan(&hasAvatarSub)
	if hasAvatarSub {
		asRows, err := legacy.QueryContext(ctx, `SELECT
			id, user_id, image_id, status, reason, note, reviewed_at, created_at
			FROM accounts_avatarsubmission ORDER BY id ASC`)
		if err == nil {
			defer asRows.Close()
			err = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
				for asRows.Next() {
					var id, uid int64
					var imgID sql.NullInt64
					var status, reason, note string
					var reviewedAt sql.NullString
					var createdAt string
					if err := asRows.Scan(&id, &uid, &imgID, &status, &reason, &note, &reviewedAt, &createdAt); err != nil {
						continue
					}
					handlingNote := note
					if reason != "" {
						if handlingNote != "" {
							handlingNote = reason + ": " + handlingNote
						} else {
							handlingNote = reason
						}
					}
					createdUTC := parseAndFormatUTC(createdAt, now)
					var revAt any
					if reviewedAt.Valid && reviewedAt.String != "" {
						revAt = parseAndFormatUTC(reviewedAt.String, now)
					}
					var imgAny any
					if imgID.Valid {
						imgAny = imgID.Int64
					}
					_, _ = tx.ExecContext(txCtx, `INSERT INTO avatar_submissions (
						id, user_id, image_id, status, handling_note, reviewed_at, created_at
					) VALUES (?, ?, ?, ?, ?, ?, ?)
					ON CONFLICT (id) DO UPDATE SET
						user_id = excluded.user_id,
						image_id = excluded.image_id,
						status = excluded.status,
						handling_note = excluded.handling_note,
						reviewed_at = excluded.reviewed_at`,
						id, uid, imgAny, status, handlingNote, revAt, createdUTC,
					)
				}
				return nil
			})
			if err != nil {
				return err
			}
		}
	}

	return nil
}
