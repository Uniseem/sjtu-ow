# 252 复核报告

## 结论

通过。M8 后台管理 API 与平台全量服务补齐（全站设置、敏感数据 Fernet 加密脱敏、平台图片/头像/队标上传与清理、审计日志多维检索、干部待办聚合、活动数据与 CSV 导出、干部手册、评论管理、旧库数据导入、API 客户端重新生成）。

## 核对项

| 检查项 | 依据 | 结果 |
|---|---|---|
| 全站设置与脱敏 | design 12.4.1、规则 186/218 | `GET /api/admin/settings` 返回全站字段，密码和接口密钥不出明文，仅输出 `has_smtp_password` 与 `has_moderation_api_key`；修改时留空保留旧值，修改成功记审计日志。 |
| 测试邮件发送 | design 12.4.1 | `POST /api/admin/settings/test-email` 验证当前配置并通过 `mail.Deliver` 发送给当前管理员，白名单与异常时有明确中文错误回显。 |
| 图片与头像上传 | design 14.1、规则 106/221 | 头像上传限制 5 次/天/人（`ratelimit.AvatarUpload`）；更换或下架头像自动清理冗余母版与缩略图；队标上传支持队长与超管，旧队标自动清理；支持 base64 JSON 与 multipart 文件双通道。 |
| 审计日志查询 | design 15.5 | `GET /api/admin/log` 联查 `users` 表操作人昵称与邮箱，支持动作、操作人、对象类型、起止时间组合过滤。 |
| 干部待办聚合 | design 10.5、规则 94/138/186 | `GET /api/admin/todo` 汇总待发信批次、未审核报名、散人待编排、过期未结赛事、未分队内战、无队长战队、审核异常及 Worker 存活状态。 |
| 活动数据统计 | design 15.6 | `GET /api/admin/activity` 支持上海时区学年计算与逐场明细，`GET /api/admin/activity/export` 生成带 UTF-8 BOM 兼容 Excel 的 CSV 文件。 |
| 干部手册与评论管理 | design 15.1、15.3 | 干部手册按角色权限输出板块；评论管理跨文章查询并支持隐藏与置顶过滤。 |
| 存量旧库兼容导入 | 12 号文档 7 | `ImportLegacyAccounts` 与 `ImportLegacySettings` 正确同步旧库头像审核记录与全站设置配置。 |
| API 客户端与检查 | 规则 D3、check.sh | `apigen` 增补全部新接口；测试机静态检查、漏洞扫描、全包单元测试与前端单元测试全绿。 |
