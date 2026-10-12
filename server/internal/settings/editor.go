package settings

import (
	"context"
	"encoding/json"
	"fmt"
	"net/mail"
	"net/url"
	"sort"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Secrets deliberately have no member in this autosave DTO. Their dedicated
// explicit operation uses the original compatible flat request instead.
type SettingsChanges struct {
	MaxGameAccounts         *int    `json:"max_game_accounts,omitempty"`
	ModerationImageEnabled  *bool   `json:"moderation_image_enabled,omitempty"`
	SiteDescription         *string `json:"site_description,omitempty"`
	FromName                *string `json:"from_name,omitempty"`
	EmailSubjectPrefix      *string `json:"email_subject_prefix,omitempty"`
	SmtpHost                *string `json:"smtp_host,omitempty"`
	SmtpPort                *int    `json:"smtp_port,omitempty"`
	SmtpSecurity            *string `json:"smtp_security,omitempty"`
	SmtpUsername            *string `json:"smtp_username,omitempty"`
	FromAddress             *string `json:"from_address,omitempty"`
	FoundedOn               *string `json:"founded_on,omitempty"`
	DefaultShareImageID     *int64  `json:"default_share_image_id,omitempty"`
	HeroImageID             *int64  `json:"hero_image_id,omitempty"`
	BannerNewsID            *int64  `json:"banner_news_id,omitempty"`
	BannerTournamentsID     *int64  `json:"banner_tournaments_id,omitempty"`
	BannerScrimsID          *int64  `json:"banner_scrims_id,omitempty"`
	BannerTeamsID           *int64  `json:"banner_teams_id,omitempty"`
	BannerMembersID         *int64  `json:"banner_members_id,omitempty"`
	QQGroupURL              *string `json:"qq_group_url,omitempty"`
	TeamMaxMembers          *int    `json:"team_max_members,omitempty"`
	TeamMaxCaptained        *int    `json:"team_max_captained,omitempty"`
	TournamentReminderHours *int    `json:"tournament_reminder_hours,omitempty"`
	ScrimReminderHours      *int    `json:"scrim_reminder_hours,omitempty"`
	ModerationEnabled       *bool   `json:"moderation_enabled,omitempty"`
	ModerationProvider      *string `json:"moderation_provider,omitempty"`
	ModerationBaseURL       *string `json:"moderation_base_url,omitempty"`
	ModerationModel         *string `json:"moderation_model,omitempty"`
	ModerationMaxTokens     *int    `json:"moderation_max_tokens,omitempty"`
	ModerationTimeoutSecs   *int    `json:"moderation_timeout_seconds,omitempty"`
	ModerationExtraParams   *string `json:"moderation_extra_params,omitempty"`
	ModerationDailyLimit    *int    `json:"moderation_daily_limit,omitempty"`
	ModerationNotifyEmail   *string `json:"moderation_notify_email,omitempty"`
}

type SettingsReceipt struct {
	Settings *SiteSettingsDTO    `json:"settings"`
	Version  int64               `json:"version"`
	Saved    []string            `json:"saved"`
	Fields   map[string][]string `json:"fields,omitempty"`
	Values   *SiteSettingsDTO    `json:"values,omitempty"`
	SavedAt  time.Time           `json:"saved_at"`
}
type SettingsCurrent struct {
	Version int64            `json:"version"`
	Values  *SiteSettingsDTO `json:"values"`
}

func (s *Service) patchFields(ctx *app.Ctx, base *int64, changes SettingsChanges) (*SettingsReceipt, error) {
	if ctx.Viewer == nil || ctx.Viewer.Disabled || !ctx.Viewer.Superuser {
		return nil, api.Forbidden()
	}
	if base == nil || *base < 1 {
		return nil, api.Invalid("保存版本无效，请重新打开页面。")
	}
	now := ctx.Now().UTC()
	receipt := &SettingsReceipt{Saved: []string{}, Fields: map[string][]string{}, SavedAt: now}
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		current, err := s.getWith(txCtx, tx)
		if err != nil {
			return err
		}
		if current.Version != *base {
			return api.Stale(SettingsCurrent{Version: current.Version, Values: current})
		}
		sets := []string{}
		args := []any{}
		set := func(field string, value any) {
			sets = append(sets, field+"=?")
			args = append(args, value)
			receipt.Saved = append(receipt.Saved, field)
		}
		reject := func(field, message string) { receipt.Fields[field] = []string{message} }
		text := func(field string, value *string, max int) {
			if value == nil {
				return
			}
			normalized := strings.TrimSpace(*value)
			if utf8.RuneCountInString(normalized) > max {
				reject(field, fmt.Sprintf("最多 %d 个字符。", max))
				return
			}
			set(field, normalized)
		}
		number := func(field string, value *int, min, max int) {
			if value == nil {
				return
			}
			if *value < min || *value > max {
				reject(field, fmt.Sprintf("请输入 %d 到 %d 之间的整数。", min, max))
				return
			}
			set(field, *value)
		}
		email := func(field string, value *string) {
			if value == nil {
				return
			}
			normalized := strings.TrimSpace(*value)
			if normalized != "" {
				address, err := mail.ParseAddress(normalized)
				if err != nil || address.Address != normalized {
					reject(field, "请输入有效的邮箱地址。")
					return
				}
			}
			set(field, normalized)
		}
		image := func(field string, value *int64) {
			if value == nil {
				return
			}
			if *value <= 0 {
				set(field, nil)
				return
			}
			var exists int
			if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM images WHERE id=?`, *value).Scan(&exists); err != nil {
				reject(field, "图片无法读取，请稍后重试。")
				return
			}
			if exists != 1 {
				reject(field, "图片不存在，请重新选择。")
				return
			}
			set(field, *value)
		}
		text("site_description", changes.SiteDescription, 500)
		text("from_name", changes.FromName, 100)
		text("email_subject_prefix", changes.EmailSubjectPrefix, 100)
		text("smtp_username", changes.SmtpUsername, 254)
		email("from_address", changes.FromAddress)
		number("smtp_port", changes.SmtpPort, 1, 65535)
		if changes.SmtpHost != nil {
			host := strings.TrimSpace(*changes.SmtpHost)
			if strings.ContainsAny(host, "/\\\r\n\t ") {
				reject("smtp_host", "请输入服务器域名，不要填写网址或空格。")
			} else {
				set("smtp_host", host)
			}
		}
		if changes.SmtpSecurity != nil {
			switch *changes.SmtpSecurity {
			case "ssl", "tls", "none", "starttls":
				set("smtp_security", *changes.SmtpSecurity)
			default:
				reject("smtp_security", "请选择有效的连接安全方式。")
			}
		}
		if changes.FoundedOn != nil {
			date := strings.TrimSpace(*changes.FoundedOn)
			if _, err := time.Parse("2006-01-02", date); date != "" && err != nil {
				reject("founded_on", "请输入有效的成立日期。")
			} else {
				set("founded_on", date)
			}
		}
		if changes.QQGroupURL != nil {
			address := strings.TrimSpace(*changes.QQGroupURL)
			parsed, err := url.Parse(address)
			if address != "" && (err != nil || parsed.Scheme != "https" || parsed.Hostname() == "" || parsed.User != nil) {
				reject("qq_group_url", "QQ 群链接必须是有效的 https:// 地址。")
			} else {
				set("qq_group_url", address)
			}
		}
		image("default_share_image_id", changes.DefaultShareImageID)
		image("hero_image_id", changes.HeroImageID)
		image("banner_news_id", changes.BannerNewsID)
		image("banner_tournaments_id", changes.BannerTournamentsID)
		image("banner_scrims_id", changes.BannerScrimsID)
		image("banner_teams_id", changes.BannerTeamsID)
		image("banner_members_id", changes.BannerMembersID)
		number("max_game_accounts", changes.MaxGameAccounts, 0, 2147483647)
		if changes.ModerationImageEnabled != nil {
			set("moderation_image_enabled", *changes.ModerationImageEnabled)
		}
		number("team_max_members", changes.TeamMaxMembers, 1, 20)
		number("team_max_captained", changes.TeamMaxCaptained, 1, 5)
		number("tournament_reminder_hours", changes.TournamentReminderHours, 0, 8760)
		number("scrim_reminder_hours", changes.ScrimReminderHours, 0, 8760)
		text("moderation_provider", changes.ModerationProvider, 64)
		text("moderation_model", changes.ModerationModel, 128)
		number("moderation_max_tokens", changes.ModerationMaxTokens, 1, 100000)
		number("moderation_timeout_seconds", changes.ModerationTimeoutSecs, 1, 300)
		number("moderation_daily_limit", changes.ModerationDailyLimit, 0, 100000)
		email("moderation_notify_email", changes.ModerationNotifyEmail)
		if changes.ModerationEnabled != nil {
			set("moderation_enabled", *changes.ModerationEnabled)
		}
		if changes.ModerationBaseURL != nil {
			address := strings.TrimSpace(*changes.ModerationBaseURL)
			parsed, err := url.Parse(address)
			if address != "" && (err != nil || parsed.Hostname() == "" || parsed.User != nil || (parsed.Scheme != "http" && parsed.Scheme != "https")) {
				reject("moderation_base_url", "请输入有效的接口地址。")
			} else {
				set("moderation_base_url", address)
			}
		}
		if changes.ModerationExtraParams != nil {
			raw := strings.TrimSpace(*changes.ModerationExtraParams)
			object := map[string]json.RawMessage{}
			if len(raw) > 10000 || raw != "" && (json.Unmarshal([]byte(raw), &object) != nil || object == nil) {
				reject("moderation_extra_params", "请填写 JSON 对象，或留空。")
			} else {
				set("moderation_extra_params", raw)
			}
		}
		if len(sets) > 0 {
			sets = append(sets, "version=version+1", "updated_at=?")
			args = append(args, db.FormatUTC(now))
			if _, err := tx.ExecContext(txCtx, `UPDATE site_settings SET `+strings.Join(sets, ",")+` WHERE id=1`, args...); err != nil {
				return err
			}
			sort.Strings(receipt.Saved)
			if err := audit.Record(txCtx, tx, ctx.Viewer.ID, "site_settings.update", "site_settings", 1, map[string]any{"fields": receipt.Saved}, now); err != nil {
				return err
			}
		}
		values, err := s.getWith(txCtx, tx)
		if err != nil {
			return err
		}
		receipt.Version = values.Version
		receipt.Values = values
		receipt.Settings = values
		return nil
	})
	if err != nil {
		return nil, err
	}
	if len(receipt.Fields) == 0 {
		receipt.Fields = nil
	}
	return receipt, nil
}
