package settings

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/crypto"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

// SiteSettingsDTO 是后台全站设置的出参模型。
type SiteSettingsDTO struct {
	ID                      int64  `json:"id"`
	SiteDescription         string `json:"site_description"`
	FromName                string `json:"from_name"`
	EmailSubjectPrefix      string `json:"email_subject_prefix"`
	SmtpHost                string `json:"smtp_host"`
	SmtpPort                int    `json:"smtp_port"`
	SmtpSecurity            string `json:"smtp_security"`
	SmtpUsername            string `json:"smtp_username"`
	HasSmtpPassword         bool   `json:"has_smtp_password"`
	FromAddress             string `json:"from_address"`
	FoundedOn               string `json:"founded_on"`
	DefaultShareImageID     *int64 `json:"default_share_image_id"`
	HeroImageID             *int64 `json:"hero_image_id"`
	BannerNewsID            *int64 `json:"banner_news_id"`
	BannerTournamentsID     *int64 `json:"banner_tournaments_id"`
	BannerScrimsID          *int64 `json:"banner_scrims_id"`
	BannerTeamsID           *int64 `json:"banner_teams_id"`
	BannerMembersID         *int64 `json:"banner_members_id"`
	QQGroupURL              string `json:"qq_group_url"`
	TeamMaxMembers          int    `json:"team_max_members"`
	TeamMaxCaptained        int    `json:"team_max_captained"`
	TournamentReminderHours int    `json:"tournament_reminder_hours"`
	ScrimReminderHours      int    `json:"scrim_reminder_hours"`
	ModerationEnabled       bool   `json:"moderation_enabled"`
	ModerationConfigured    bool   `json:"moderation_configured"`
	ModerationProvider      string `json:"moderation_provider"`
	HasModerationAPIKey     bool   `json:"has_moderation_api_key"`
	ModerationBaseURL       string `json:"moderation_base_url"`
	ModerationModel         string `json:"moderation_model"`
	ModerationMaxTokens     int    `json:"moderation_max_tokens"`
	ModerationTimeoutSecs   int    `json:"moderation_timeout_seconds"`
	ModerationExtraParams   string `json:"moderation_extra_params"`
	ModerationDailyLimit    int    `json:"moderation_daily_limit"`
	ModerationNotifyEmail   string `json:"moderation_notify_email"`
	Version                 int64  `json:"version"`
	UpdatedAt               string `json:"updated_at"`
}

// UpdateSettingsInput 是修改全站设置的入参。
type UpdateSettingsInput struct {
	SiteDescription         *string `json:"site_description,omitempty"`
	FromName                *string `json:"from_name,omitempty"`
	EmailSubjectPrefix      *string `json:"email_subject_prefix,omitempty"`
	SmtpHost                *string `json:"smtp_host,omitempty"`
	SmtpPort                *int    `json:"smtp_port,omitempty"`
	SmtpSecurity            *string `json:"smtp_security,omitempty"`
	SmtpUsername            *string `json:"smtp_username,omitempty"`
	SmtpPassword            *string `json:"smtp_password,omitempty"`
	ClearSmtpPassword       *bool   `json:"clear_smtp_password,omitempty"`
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
	ModerationAPIKey        *string `json:"moderation_api_key,omitempty"`
	ClearModerationAPIKey   *bool   `json:"clear_moderation_api_key,omitempty"`
	ModerationBaseURL       *string `json:"moderation_base_url,omitempty"`
	ModerationModel         *string `json:"moderation_model,omitempty"`
	ModerationMaxTokens     *int    `json:"moderation_max_tokens,omitempty"`
	ModerationTimeoutSecs   *int    `json:"moderation_timeout_seconds,omitempty"`
	ModerationExtraParams   *string `json:"moderation_extra_params,omitempty"`
	ModerationDailyLimit    *int    `json:"moderation_daily_limit,omitempty"`
	ModerationNotifyEmail   *string `json:"moderation_notify_email,omitempty"`
}

// Service 负责全站设置读写与邮件测试。
type Service struct {
	d        *db.DB
	siteURL  string
	fieldKey string
}

// NewService 创建全站设置服务。
func NewService(d *db.DB, siteURL, fieldKey string) *Service {
	return &Service{
		d:        d,
		siteURL:  siteURL,
		fieldKey: fieldKey,
	}
}

// Get 读取全站设置。
func (s *Service) Get(ctx context.Context) (*SiteSettingsDTO, error) {
	row := s.d.ReadPool().QueryRowContext(ctx, `
		SELECT id, site_description, from_name, email_subject_prefix,
		       smtp_host, smtp_port, smtp_security, smtp_username, smtp_password, from_address,
		       founded_on, default_share_image_id, hero_image_id,
		       banner_news_id, banner_tournaments_id, banner_scrims_id, banner_teams_id, banner_members_id,
		       qq_group_url, team_max_members, team_max_captained, tournament_reminder_hours, scrim_reminder_hours,
		       moderation_enabled, moderation_configured, moderation_provider, moderation_api_key,
		       moderation_base_url, moderation_model, moderation_max_tokens, moderation_timeout_seconds,
		       moderation_extra_params, moderation_daily_limit, moderation_notify_email,
		       version, updated_at
		FROM site_settings WHERE id = 1
	`)

	var dto SiteSettingsDTO
	var smtpPass, modKey string
	var modEnabled, modConfigured int
	var defShare, hero, bNews, bTourn, bScrim, bTeams, bMemb sql.NullInt64

	err := row.Scan(
		&dto.ID, &dto.SiteDescription, &dto.FromName, &dto.EmailSubjectPrefix,
		&dto.SmtpHost, &dto.SmtpPort, &dto.SmtpSecurity, &dto.SmtpUsername, &smtpPass, &dto.FromAddress,
		&dto.FoundedOn, &defShare, &hero,
		&bNews, &bTourn, &bScrim, &bTeams, &bMemb,
		&dto.QQGroupURL, &dto.TeamMaxMembers, &dto.TeamMaxCaptained, &dto.TournamentReminderHours, &dto.ScrimReminderHours,
		&modEnabled, &modConfigured, &dto.ModerationProvider, &modKey,
		&dto.ModerationBaseURL, &dto.ModerationModel, &dto.ModerationMaxTokens, &dto.ModerationTimeoutSecs,
		&dto.ModerationExtraParams, &dto.ModerationDailyLimit, &dto.ModerationNotifyEmail,
		&dto.Version, &dto.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("读取全站设置失败: %w", err)
	}

	dto.HasSmtpPassword = smtpPass != ""
	dto.HasModerationAPIKey = modKey != ""
	dto.ModerationEnabled = modEnabled != 0
	dto.ModerationConfigured = modConfigured != 0

	if defShare.Valid {
		v := defShare.Int64
		dto.DefaultShareImageID = &v
	}
	if hero.Valid {
		v := hero.Int64
		dto.HeroImageID = &v
	}
	if bNews.Valid {
		v := bNews.Int64
		dto.BannerNewsID = &v
	}
	if bTourn.Valid {
		v := bTourn.Int64
		dto.BannerTournamentsID = &v
	}
	if bScrim.Valid {
		v := bScrim.Int64
		dto.BannerScrimsID = &v
	}
	if bTeams.Valid {
		v := bTeams.Int64
		dto.BannerTeamsID = &v
	}
	if bMemb.Valid {
		v := bMemb.Int64
		dto.BannerMembersID = &v
	}

	return &dto, nil
}

// Update 更新全站设置。
func (s *Service) Update(ctx *app.Ctx, in UpdateSettingsInput) (*SiteSettingsDTO, error) {
	if ctx.Viewer == nil || !ctx.Viewer.Superuser {
		return nil, api.Forbidden()
	}

	// 校验
	if in.QQGroupURL != nil && *in.QQGroupURL != "" {
		trimmed := strings.TrimSpace(*in.QQGroupURL)
		if !strings.HasPrefix(strings.ToLower(trimmed), "https://") {
			return nil, api.InvalidFields(map[string][]string{
				"qq_group_url": {"QQ 群链接必须以 https:// 开头。"},
			})
		}
	}
	if in.TeamMaxMembers != nil && (*in.TeamMaxMembers < 1 || *in.TeamMaxMembers > 20) {
		return nil, api.InvalidFields(map[string][]string{
			"team_max_members": {"战队人数上限必须在 1 到 20 之间。"},
		})
	}
	if in.TeamMaxCaptained != nil && (*in.TeamMaxCaptained < 1 || *in.TeamMaxCaptained > 5) {
		return nil, api.InvalidFields(map[string][]string{
			"team_max_captained": {"同时担任队长上限必须在 1 到 5 之间。"},
		})
	}
	if in.TournamentReminderHours != nil && *in.TournamentReminderHours < 0 {
		return nil, api.InvalidFields(map[string][]string{
			"tournament_reminder_hours": {"提醒小时数不能为负数。"},
		})
	}
	if in.ScrimReminderHours != nil && *in.ScrimReminderHours < 0 {
		return nil, api.InvalidFields(map[string][]string{
			"scrim_reminder_hours": {"提醒小时数不能为负数。"},
		})
	}

	now := ctx.Now().UTC()
	var updated *SiteSettingsDTO

	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		// 先读取现有数据
		var currentSmtpPass, currentModKey string
		var currentModConfigured int
		var currentModBaseURL string
		err := tx.QueryRowContext(txCtx, `
			SELECT smtp_password, moderation_api_key, moderation_configured, moderation_base_url
			FROM site_settings WHERE id = 1
		`).Scan(&currentSmtpPass, &currentModKey, &currentModConfigured, &currentModBaseURL)
		if err != nil {
			return fmt.Errorf("读取旧全站设置失败: %w", err)
		}

		// 密码处理
		newSmtpPass := currentSmtpPass
		if in.ClearSmtpPassword != nil && *in.ClearSmtpPassword {
			newSmtpPass = ""
		} else if in.SmtpPassword != nil && *in.SmtpPassword != "" {
			enc, err := crypto.Encrypt(s.fieldKey, *in.SmtpPassword)
			if err != nil {
				return fmt.Errorf("加密 SMTP 密码失败: %w", err)
			}
			newSmtpPass = enc
		}

		// 审核 Key 处理
		newModKey := currentModKey
		if in.ClearModerationAPIKey != nil && *in.ClearModerationAPIKey {
			newModKey = ""
		} else if in.ModerationAPIKey != nil && *in.ModerationAPIKey != "" {
			enc, err := crypto.Encrypt(s.fieldKey, *in.ModerationAPIKey)
			if err != nil {
				return fmt.Errorf("加密审核 API Key 失败: %w", err)
			}
			newModKey = enc
		}

		newModBaseURL := currentModBaseURL
		if in.ModerationBaseURL != nil {
			newModBaseURL = strings.TrimSpace(*in.ModerationBaseURL)
		}
		newModConfigured := 0
		if newModKey != "" || newModBaseURL != "" {
			newModConfigured = 1
		}

		// 构建更新语句
		cols := []string{
			"updated_at = ?",
			"version = version + 1",
			"smtp_password = ?",
			"moderation_api_key = ?",
			"moderation_configured = ?",
		}
		args := []any{
			db.FormatUTC(now),
			newSmtpPass,
			newModKey,
			newModConfigured,
		}

		if in.SiteDescription != nil {
			cols = append(cols, "site_description = ?")
			args = append(args, strings.TrimSpace(*in.SiteDescription))
		}
		if in.FromName != nil {
			cols = append(cols, "from_name = ?")
			args = append(args, strings.TrimSpace(*in.FromName))
		}
		if in.EmailSubjectPrefix != nil {
			cols = append(cols, "email_subject_prefix = ?")
			args = append(args, strings.TrimSpace(*in.EmailSubjectPrefix))
		}
		if in.SmtpHost != nil {
			cols = append(cols, "smtp_host = ?")
			args = append(args, strings.TrimSpace(*in.SmtpHost))
		}
		if in.SmtpPort != nil {
			cols = append(cols, "smtp_port = ?")
			args = append(args, *in.SmtpPort)
		}
		if in.SmtpSecurity != nil {
			cols = append(cols, "smtp_security = ?")
			args = append(args, strings.TrimSpace(*in.SmtpSecurity))
		}
		if in.SmtpUsername != nil {
			cols = append(cols, "smtp_username = ?")
			args = append(args, strings.TrimSpace(*in.SmtpUsername))
		}
		if in.FromAddress != nil {
			cols = append(cols, "from_address = ?")
			args = append(args, strings.TrimSpace(*in.FromAddress))
		}
		if in.FoundedOn != nil {
			cols = append(cols, "founded_on = ?")
			args = append(args, strings.TrimSpace(*in.FoundedOn))
		}
		if in.DefaultShareImageID != nil {
			cols = append(cols, "default_share_image_id = ?")
			if *in.DefaultShareImageID > 0 {
				args = append(args, *in.DefaultShareImageID)
			} else {
				args = append(args, nil)
			}
		}
		if in.HeroImageID != nil {
			cols = append(cols, "hero_image_id = ?")
			if *in.HeroImageID > 0 {
				args = append(args, *in.HeroImageID)
			} else {
				args = append(args, nil)
			}
		}
		if in.BannerNewsID != nil {
			cols = append(cols, "banner_news_id = ?")
			if *in.BannerNewsID > 0 {
				args = append(args, *in.BannerNewsID)
			} else {
				args = append(args, nil)
			}
		}
		if in.BannerTournamentsID != nil {
			cols = append(cols, "banner_tournaments_id = ?")
			if *in.BannerTournamentsID > 0 {
				args = append(args, *in.BannerTournamentsID)
			} else {
				args = append(args, nil)
			}
		}
		if in.BannerScrimsID != nil {
			cols = append(cols, "banner_scrims_id = ?")
			if *in.BannerScrimsID > 0 {
				args = append(args, *in.BannerScrimsID)
			} else {
				args = append(args, nil)
			}
		}
		if in.BannerTeamsID != nil {
			cols = append(cols, "banner_teams_id = ?")
			if *in.BannerTeamsID > 0 {
				args = append(args, *in.BannerTeamsID)
			} else {
				args = append(args, nil)
			}
		}
		if in.BannerMembersID != nil {
			cols = append(cols, "banner_members_id = ?")
			if *in.BannerMembersID > 0 {
				args = append(args, *in.BannerMembersID)
			} else {
				args = append(args, nil)
			}
		}
		if in.QQGroupURL != nil {
			cols = append(cols, "qq_group_url = ?")
			args = append(args, strings.TrimSpace(*in.QQGroupURL))
		}
		if in.TeamMaxMembers != nil {
			cols = append(cols, "team_max_members = ?")
			args = append(args, *in.TeamMaxMembers)
		}
		if in.TeamMaxCaptained != nil {
			cols = append(cols, "team_max_captained = ?")
			args = append(args, *in.TeamMaxCaptained)
		}
		if in.TournamentReminderHours != nil {
			cols = append(cols, "tournament_reminder_hours = ?")
			args = append(args, *in.TournamentReminderHours)
		}
		if in.ScrimReminderHours != nil {
			cols = append(cols, "scrim_reminder_hours = ?")
			args = append(args, *in.ScrimReminderHours)
		}
		if in.ModerationEnabled != nil {
			cols = append(cols, "moderation_enabled = ?")
			val := 0
			if *in.ModerationEnabled {
				val = 1
			}
			args = append(args, val)
		}
		if in.ModerationProvider != nil {
			cols = append(cols, "moderation_provider = ?")
			args = append(args, strings.TrimSpace(*in.ModerationProvider))
		}
		if in.ModerationBaseURL != nil {
			cols = append(cols, "moderation_base_url = ?")
			args = append(args, strings.TrimSpace(*in.ModerationBaseURL))
		}
		if in.ModerationModel != nil {
			cols = append(cols, "moderation_model = ?")
			args = append(args, strings.TrimSpace(*in.ModerationModel))
		}
		if in.ModerationMaxTokens != nil {
			cols = append(cols, "moderation_max_tokens = ?")
			args = append(args, *in.ModerationMaxTokens)
		}
		if in.ModerationTimeoutSecs != nil {
			cols = append(cols, "moderation_timeout_seconds = ?")
			args = append(args, *in.ModerationTimeoutSecs)
		}
		if in.ModerationExtraParams != nil {
			cols = append(cols, "moderation_extra_params = ?")
			args = append(args, strings.TrimSpace(*in.ModerationExtraParams))
		}
		if in.ModerationDailyLimit != nil {
			cols = append(cols, "moderation_daily_limit = ?")
			args = append(args, *in.ModerationDailyLimit)
		}
		if in.ModerationNotifyEmail != nil {
			cols = append(cols, "moderation_notify_email = ?")
			args = append(args, strings.TrimSpace(*in.ModerationNotifyEmail))
		}

		query := fmt.Sprintf("UPDATE site_settings SET %s WHERE id = 1", strings.Join(cols, ", "))
		if _, err := tx.ExecContext(txCtx, query, args...); err != nil {
			return fmt.Errorf("更新全站设置失败: %w", err)
		}

		// 记审计日志
		if err := audit.Record(txCtx, tx, ctx.Viewer.ID, "site_settings.update", "site_settings", 1, in, now); err != nil {
			return fmt.Errorf("记录审计日志失败: %w", err)
		}

		return nil
	})
	if err != nil {
		return nil, err
	}

	updated, err = s.Get(ctx.Context)
	return updated, err
}

// SendTestEmail 发送一封测试邮件到当前管理员邮箱。
func (s *Service) SendTestEmail(ctx *app.Ctx) (string, error) {
	if ctx.Viewer == nil || !ctx.Viewer.Superuser {
		return "", api.Forbidden()
	}

	var host, user, pass, from, sec, prefix, name string
	var port int
	err := s.d.ReadPool().QueryRowContext(ctx.Context, `
		SELECT smtp_host, smtp_port, smtp_security, smtp_username, smtp_password, from_address, from_name, email_subject_prefix
		FROM site_settings WHERE id = 1
	`).Scan(&host, &port, &sec, &user, &pass, &from, &name, &prefix)
	if err != nil {
		return "", fmt.Errorf("读取 SMTP 设置失败: %w", err)
	}

	if host == "" || from == "" {
		return "", errors.New("后台尚未配置 SMTP 服务器或发件地址，请先在全站设置中填写并保存。")
	}

	decPass := ""
	if pass != "" {
		p, err := crypto.Decrypt(s.fieldKey, pass)
		if err != nil {
			return "", fmt.Errorf("解密 SMTP 密码失败: %w", err)
		}
		decPass = p
	}

	cfg := mail.SMTP{
		Host:     host,
		Port:     port,
		Username: user,
		Password: decPass,
		FromName: name,
		FromAddr: from,
		Security: sec,
		Prefix:   prefix,
		Timeout:  15 * time.Second,
	}

	target := mail.Person{
		Name:    ctx.Viewer.Nickname,
		Address: ctx.Viewer.Email,
	}
	if target.Address == "" {
		return "", errors.New("当前账号没有绑定邮箱，无法发送测试邮件。")
	}

	letter := mail.Letter{
		Subject:    "测试邮件",
		Lead:       "这是一封来自 SJTU-OW 管理后台的测试邮件。看到这封信说明网站的 SMTP 发信配置一切正常。",
		Paragraphs: []string{"测试时间：" + ctx.Now().In(time.FixedZone("Asia/Shanghai", 8*3600)).Format("2006-01-02 15:04:05")},
	}

	skipped, err := mail.Deliver(ctx.Context, cfg, letter, target, s.siteURL, ctx.Now())
	if err != nil {
		return "", fmt.Errorf("发信失败：%w", err)
	}
	if skipped {
		return "", errors.New("由于邮箱白名单限制，测试邮件被跳过未发送。")
	}

	return fmt.Sprintf("测试邮件已成功发送到 %s。", target.Address), nil
}
