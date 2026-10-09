# 251 自查与复核

## 自查清单

1. **待发信与批次机制**：
   - 是否所有登录用户写请求都初始化了 `Letters` 批次？是的，`method != GET && viewer != nil && viewer.ID > 0 && !viewer.Disabled` 均开启。
   - 动作若未产生信件，响应是否干净（不含多余 `letters` 字段）？是的，仅当 `batch.Held > 0` 且用户未注销时注入。
   - 用户在请求过程中注销（如 `delete-account`），信件如何处理？`settleLetters` 检测到 `ctx.ShouldClearSessionCookie()` 时，自动调用 `outbox.SendAll` 由系统代发并记入审计，对前端不返回 `letters` 对象。
   - 待发信是否支持跳过和防重复？是的，`DecideHeld` 校验原子状态并更新 `state = 'sent'` 或 `'skipped'`，第二次提交什么都不发。

2. **全员公告与 30 分钟冷却**：
   - 冷却时间是否准确？30 分钟，且状态和报错信息中均包含具体上次北京时间（如 "20:00 刚通知过全体成员，30 分钟内不再发。"）。
   - 定时上线文章是否会提前发信？不会，`waits_for_publish = 1` 仅挂起记录，直到文章正式发布（立即发布或定时任务触发上线）时通过 `SendWaiting` 激活投递。
   - 投递时是否按收件人单独生成退订链接？是的，在 `notify.deliver` 执行时重新拉取接受通知的会员列表，逐一用专属签名 Token 构造退订 URL，确保信件独立。

3. **退订体系**：
   - 退订 Token 是否防篡改且不可逆？是的，使用 `djsign.Dumps` 配合专属 Salt 和项目签名密钥签名。
   - RFC 8058 邮件客户端一键退订是否支持？是的，使用 `api.Raw` 注册 `POST /unsubscribe/{token}/{$}`，且套用 `Unsubscribe` 限流规则。
   - 账号停用后退订链接是否失效？是的，`userFor` 中包含 `is_active = 1` 条件。

4. **手机日历订阅**：
   - 订阅链接生成与换新：`Renew` 原子递增 `calendar_version`，旧地址由于版本不匹配立即 404。
   - RFC 5545 规范：每行平滑折叠，75 字节限制，且折叠行以空格开头，不破坏中文字符。
   - 安排时间计算：内战正在打（-6小时内）或未开始的均保留；赛事已报名或散人池均保留；已过期赛事自动排除；无开始时间的排在最后。
   - 限流：日历订阅路由挂载 `CalendarFeed`（30次/分/IP）。

5. **存量导入与兼容性**：
   - `accounts_user` 导入已同步更新 `accepts_announcements` 和 `calendar_version`，保证平滑割接。
