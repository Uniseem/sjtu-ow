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
    { name: 'site_description', label: "站点简介", kind: 'textarea', help: "用于页面描述和链接预览。" },
    { name: 'founded_on', label: "社区成立日期", kind: 'date', help: "首页数字条「社区已成立 N 年 M 天」按它算；空着不显示这一项。" },
    { name: 'qq_group_url', label: "QQ 群链接", kind: 'url', help: "QQ 群的分享链接，https:// 开头。首页首屏的「加入 QQ 群」按钮链接到这里；空着不显示。" },
  ] },
  { title: '邮件发送', fields: [
    { name: 'from_name', label: "发件人名称", kind: 'text', required: true, maxlength: 100 },
    { name: 'from_address', label: "发件地址", kind: 'email' },
    { name: 'email_subject_prefix', label: "邮件主题前缀", kind: 'text', required: true, maxlength: 40 },
    { name: 'smtp_host', label: "SMTP 服务器", kind: 'text', maxlength: 255 },
    { name: 'smtp_port', label: "SMTP 端口", kind: 'number', min: 1, max: 65535, required: true },
    { name: 'smtp_security', label: "加密方式", kind: 'select', choices: [{ value: 'starttls', label: 'STARTTLS' }, { value: 'ssl', label: 'SSL' }, { value: 'none', label: '无' }], required: true, maxlength: 16 },
    { name: 'smtp_username', label: "SMTP 账号", kind: 'text', maxlength: 255 },
  ] },
  { title: '社区参数', fields: [
    { name: 'max_game_accounts', label: "每人最多游戏 ID", kind: 'number', min: 0, max: 2147483647, required: true },
    { name: 'team_max_members', label: "战队人数上限", kind: 'number', min: 1, help: "一支战队最多多少人，含队长。", required: true },
    { name: 'team_max_captained', label: "每人最多担任队长数", kind: 'number', min: 1, help: "每人最多同时担任几支战队的队长。", required: true },
    { name: 'tournament_reminder_hours', label: "赛事提前提醒小时数", kind: 'number', min: 0, help: "填了比赛时间的赛事，开始前多久给已通过报名的队员发提醒邮件。", required: true },
    { name: 'scrim_reminder_hours', label: "内战提前提醒小时数", kind: 'number', min: 0, help: "内战开始前多久给报名者发提醒邮件。", required: true },
  ] },
  { title: 'AI 审核', fields: [
    { name: 'moderation_image_enabled', label: "连图片一起审核", kind: 'checkbox', help: "开启后投稿里的图片也送审，费用更高。" },
    { name: 'moderation_enabled', label: "启用 AI 内容审核", kind: 'checkbox', help: "关掉后新内容不再送审。没有填接口密钥（或接口地址）时本来就不送审。" },
    { name: 'moderation_base_url', label: "接口地址", kind: 'url', help: "空着用 DeepSeek（https://api.deepseek.com/v1）。换服务商、用聚合平台或自建服务时填它的 OpenAI 兼容地址，一般以 /v1 结尾。" },
    { name: 'moderation_model', label: "审核模型", kind: 'text', help: "服务商接口里的模型名。", required: true, maxlength: 100 },
    { name: 'moderation_extra_params', label: "附加请求参数", kind: 'textarea', help: "一段 JSON，原样并进每次请求，比如关闭思考模式的参数（各家写法不一样，照服务商的文档填）。不知道就空着。" },
    { name: 'moderation_timeout_seconds', label: "超时（秒）", kind: 'number', min: 1, help: "一次调用最多等多久。", required: true },
    { name: 'moderation_max_tokens', label: "最多输出 token", kind: 'number', min: 1, help: "一次调用最多让模型写多少，几百就够。", required: true },
    { name: 'moderation_daily_limit', label: "审核每日调用上限", kind: 'number', min: 0, help: "每天最多调用多少次审核接口，超出的排到第二天再审（5.5.3）。", required: true },
    { name: 'moderation_notify_email', label: "巡查提醒发到", kind: 'email', help: "AI 每 30 分钟巡查一次，发现可能不妥的内容就给这个邮箱发信。空着就发给所有超级管理员。" },
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
