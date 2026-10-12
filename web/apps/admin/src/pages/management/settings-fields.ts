import type { GetApiAdminSettingsOut } from "@sjtu-ow/api"
export type Settings = NonNullable<GetApiAdminSettingsOut['settings']>
export type SettingsValues = Pick<Settings,
  'max_game_accounts' | 'moderation_image_enabled' | 'site_description' | 'from_name' | 'email_subject_prefix' | 'smtp_host' | 'smtp_port' | 'smtp_security' | 'smtp_username' | 'from_address' | 'founded_on' | 'qq_group_url' |
  'team_max_members' | 'team_max_captained' | 'tournament_reminder_hours' | 'scrim_reminder_hours' |
  'moderation_enabled' | 'moderation_provider' | 'moderation_base_url' | 'moderation_model' | 'moderation_max_tokens' | 'moderation_timeout_seconds' | 'moderation_extra_params' | 'moderation_daily_limit' | 'moderation_notify_email'>
export type SettingField = { name: keyof SettingsValues; label: string; kind: 'text' | 'number' | 'email' | 'url' | 'date' | 'textarea' | 'checkbox' | 'select'; help?: string; min?: number; max?: number; choices?: { value: string; label: string }[] }
export type SettingSection = { title: string; fields: SettingField[] }
export const settingsSections: SettingSection[] = [
  { title: '站点信息', fields: [
    { name: 'site_description', label: '网站简介', kind: 'textarea' },
    { name: 'founded_on', label: '成立日期', kind: 'date' },
    { name: 'qq_group_url', label: 'QQ 群链接', kind: 'url' },
  ] },
  { title: '邮件发送', fields: [
    { name: 'from_name', label: '发信人名称', kind: 'text' },
    { name: 'from_address', label: '发信邮箱', kind: 'email' },
    { name: 'email_subject_prefix', label: '邮件主题前缀', kind: 'text' },
    { name: 'smtp_host', label: 'SMTP 服务器', kind: 'text' },
    { name: 'smtp_port', label: 'SMTP 端口', kind: 'number', min: 1, max: 65535 },
    { name: 'smtp_security', label: '连接安全', kind: 'select', choices: [{ value: 'starttls', label: 'STARTTLS' }, { value: 'ssl', label: 'SSL/TLS' }, { value: 'none', label: '无' }] },
    { name: 'smtp_username', label: 'SMTP 用户名', kind: 'text' },
  ] },
  { title: '社区参数', fields: [
    { name: 'max_game_accounts', label: '每人最多游戏 ID', kind: 'number', min: 0, max: 2147483647 },
    { name: 'team_max_members', label: '战队人数上限', kind: 'number', min: 1 },
    { name: 'team_max_captained', label: '每人担任队长上限', kind: 'number', min: 1 },
    { name: 'tournament_reminder_hours', label: '赛事提前提醒（小时）', kind: 'number', min: 0 },
    { name: 'scrim_reminder_hours', label: '内战提前提醒（小时）', kind: 'number', min: 0 },
  ] },
  { title: 'AI 审核', fields: [
    { name: 'moderation_image_enabled', label: '送审正文里的图片', kind: 'checkbox' },
    { name: 'moderation_enabled', label: '启用 AI 内容审核', kind: 'checkbox' },
    { name: 'moderation_provider', label: '服务商', kind: 'text' },
    { name: 'moderation_base_url', label: '接口地址', kind: 'url' },
    { name: 'moderation_model', label: '模型', kind: 'text' },
    { name: 'moderation_extra_params', label: '附加请求参数', kind: 'textarea', help: 'JSON 对象。留空使用默认参数。' },
    { name: 'moderation_timeout_seconds', label: '超时（秒）', kind: 'number', min: 1 },
    { name: 'moderation_max_tokens', label: '最多输出 token', kind: 'number', min: 1 },
    { name: 'moderation_daily_limit', label: '每日调用上限', kind: 'number', min: 0 },
    { name: 'moderation_notify_email', label: '巡查通知邮箱', kind: 'email' },
  ] },
]
export function settingsValues(settings: Settings): SettingsValues {
  return {
    max_game_accounts:settings.max_game_accounts,moderation_image_enabled:settings.moderation_image_enabled,site_description: settings.site_description, from_name: settings.from_name, from_address: settings.from_address,
    email_subject_prefix: settings.email_subject_prefix, smtp_host: settings.smtp_host, smtp_port: settings.smtp_port,
    smtp_security: settings.smtp_security, smtp_username: settings.smtp_username, founded_on: settings.founded_on,
    qq_group_url: settings.qq_group_url, team_max_members: settings.team_max_members, team_max_captained: settings.team_max_captained,
    tournament_reminder_hours: settings.tournament_reminder_hours, scrim_reminder_hours: settings.scrim_reminder_hours,
    moderation_enabled: settings.moderation_enabled, moderation_provider: settings.moderation_provider,
    moderation_base_url: settings.moderation_base_url, moderation_model: settings.moderation_model,
    moderation_max_tokens: settings.moderation_max_tokens, moderation_timeout_seconds: settings.moderation_timeout_seconds,
    moderation_extra_params: settings.moderation_extra_params, moderation_daily_limit: settings.moderation_daily_limit,
    moderation_notify_email: settings.moderation_notify_email,
  }
}
