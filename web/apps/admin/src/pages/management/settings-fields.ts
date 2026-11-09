import type { GetApiAdminSettingsOut } from "@sjtu-ow/api"
export type Settings = NonNullable<GetApiAdminSettingsOut['settings']>
export type SettingsValues = Pick<Settings,
  'max_game_accounts' | 'moderation_image_enabled' | 'site_description' | 'from_name' | 'email_subject_prefix' | 'smtp_host' | 'smtp_port' | 'smtp_security' | 'smtp_username' | 'from_address' | 'founded_on' | 'qq_group_url' |
  'team_max_members' | 'team_max_captained' | 'tournament_reminder_hours' | 'scrim_reminder_hours' |
  'moderation_enabled' | 'moderation_provider' | 'moderation_base_url' | 'moderation_model' | 'moderation_max_tokens' | 'moderation_timeout_seconds' | 'moderation_extra_params' | 'moderation_daily_limit' | 'moderation_notify_email'>
export type SettingField = { name: keyof SettingsValues; label: string; kind: 'text' | 'number' | 'email' | 'url' | 'date' | 'textarea' | 'checkbox' | 'select'; help?: string; required?: boolean; maxlength?: number; min?: number; max?: number; choices?: { value: string; label: string }[] }
export type SettingSection = { title: string; fields: SettingField[] }
export const settingsSections: SettingSection[] = [
  { title: '站点信息', fields: [
    { name: 'site_description', label: "站点简介", kind: 'textarea' },
    { name: 'founded_on', label: "社区成立日期", kind: 'date' },
    { name: 'qq_group_url', label: "QQ 群链接", kind: 'url' },
  ] },
  { title: '邮件发送', fields: [
    { name: 'from_name', label: "发件人名称", kind: 'text', required: true, maxlength: 100 },
    { name: 'from_address', label: "发件地址", kind: 'email' },
    { name: 'email_subject_prefix', label: "邮件主题前缀", kind: 'text', required: true, maxlength: 40 },
    { name: 'smtp_host', label: "SMTP 服务器", kind: 'text', maxlength: 255 },
    { name: 'smtp_port', label: "SMTP 端口", kind: 'number', min: 1, max: 65535, required: true },
    { name: 'smtp_security', label: "加密方式", kind: 'select', choices: [{ value: 'none', label: '无' }, { value: 'starttls', label: 'STARTTLS' }, { value: 'ssl', label: 'SSL' }], required: true, maxlength: 16 },
    { name: 'smtp_username', label: "SMTP 账号", kind: 'text', maxlength: 255 },
  ] },
  { title: '社区参数', fields: [
    { name: 'max_game_accounts', label: "每人最多游戏 ID", kind: 'number', min: 0, max: 2147483647, required: true },
    { name: 'team_max_members', label: "战队人数上限（含队长）", kind: 'number', min: 1, required: true },
    { name: 'team_max_captained', label: "每人最多担任队长数", kind: 'number', min: 1, required: true },
    { name: 'tournament_reminder_hours', label: "赛事提前提醒小时数", kind: 'number', min: 0, required: true },
    { name: 'scrim_reminder_hours', label: "内战提前提醒小时数", kind: 'number', min: 0, required: true },
  ] },
  { title: 'AI 审核', fields: [
    { name: 'moderation_image_enabled', label: "连图片一起审核", kind: 'checkbox', help: "图片送审会增加费用。" },
    { name: 'moderation_enabled', label: "启用 AI 内容审核", kind: 'checkbox', help: "巡查暂不可用，配置仅保存备用。" },
    { name: 'moderation_base_url', label: "接口地址", kind: 'url', help: "OpenAI 兼容地址，留空使用 DeepSeek。" },
    { name: 'moderation_model', label: "审核模型", kind: 'text', required: true, maxlength: 100 },
    { name: 'moderation_extra_params', label: "附加请求参数", kind: 'textarea', help: "JSON，可留空。" },
    { name: 'moderation_timeout_seconds', label: "超时（秒）", kind: 'number', min: 1, required: true },
    { name: 'moderation_max_tokens', label: "最多输出 token", kind: 'number', min: 1, required: true },
    { name: 'moderation_daily_limit', label: "审核每日调用上限", kind: 'number', min: 0, help: "超额部分次日处理。", required: true },
    { name: 'moderation_notify_email', label: "巡查提醒发到", kind: 'email', help: "留空通知所有超级管理员。" },
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
