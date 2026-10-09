package ratelimit

import "time"

// 数字集中在这一张表（12 号文档 5.9：和设计附录 C 对照，测试钉住）。
// 注册接口时只许引用这里的变量，不许内联数字——这是「一张表」的结构性保证。
//
// 还没进表、数字先记在这里（等对应接口的轮次再引用，免得对照时丢掉）：
//
//	规则 215 页面状态片段 120/分/IP（新栈没有预渲染片段，接口落地时再定要不要）
//	规则 221 头像上传 5/天/人（M4 图片）
//
// login_failed 的 10/分/IP（规则 6）没有单独建桶（241）：30/分/IP 的总量和
// 5 次/300 秒/账号的定向爆破防线合起来已覆盖它的语义，多一条同维度的 IP 桶
// 只会让正常用户更早撞墙。取舍记录在这里，对照规则 6 时看这段。
var (
	// AuthSignup 用户注册：每个 IP 每分钟 20 次（规则 6，allauth: signup 20/m/ip）
	AuthSignup = Decl{Name: "auth_signup", Kind: PerIP, N: 20, Window: time.Minute}

	// AuthLogin 登录：每个 IP 每分钟 30 次（规则 6，allauth: login 30/m/ip）
	AuthLogin = Decl{Name: "auth_login", Kind: PerIP, N: 30, Window: time.Minute}

	// AuthLoginFailedKey 登录失败：同一账号 300 秒内 5 次（规则 6，allauth:
	// login_failed 5/300s/key）。key 由服务层自己拼（"email:"+规范化邮箱），
	// 密码错的那次才计数；第 6 次起 429，直到时间片翻页。
	AuthLoginFailedKey = Decl{Name: "auth_login_failed_key", Kind: PerKey, N: 5, Window: 5 * time.Minute}

	// AuthVerifyEmail 核验邮箱验证码：每个 IP 每分钟 10 次。码本身的
	// 3 次尝试限制（R002，email_codes.attempts）是主防线，这条只挡乱试脚本
	// （allauth 的 confirm_email 1/10s/key 是确认链接，语义不同，不照搬）。
	AuthVerifyEmail = Decl{Name: "auth_verify_email", Kind: PerIP, N: 10, Window: time.Minute}

	// AuthResendEmailCode 重新发送邮箱验证码：每个 IP 每分钟 10 次（防发信轰炸）。
	AuthResendEmailCode = Decl{Name: "auth_resend_email_code", Kind: PerIP, N: 10, Window: time.Minute}

	// AuthResendEmailCodeKey 重新发送邮箱验证码：同一账号 10 秒内最多 1 次（规则 6，allauth:
	// confirm_email 1/10s/key）。key 由服务层拼（"email:"+规范化邮箱）；第 2 次起 429。
	AuthResendEmailCodeKey = Decl{Name: "auth_resend_email_code_key", Kind: PerKey, N: 1, Window: 10 * time.Second}

	// AuthResetPassword 找回密码发码：每个 IP 每分钟 20 次（规则 6，allauth: reset_password 20/m/ip）。
	AuthResetPassword = Decl{Name: "auth_reset_password", Kind: PerIP, N: 20, Window: time.Minute}

	// AuthResetPasswordKey 找回密码发码：同一账号每分钟最多 5 次（规则 6，allauth: reset_password 5/m/key）。
	// key 由服务层拼（"email:"+规范化邮箱）；第 6 次起 429。
	AuthResetPasswordKey = Decl{Name: "auth_reset_password_key", Kind: PerKey, N: 5, Window: time.Minute}

	// AuthResetPasswordConfirm 核验重置密码：每个 IP 每分钟 20 次（规则 6，allauth: reset_password_from_key 20/m/ip）。
	AuthResetPasswordConfirm = Decl{Name: "auth_reset_password_confirm", Kind: PerIP, N: 20, Window: time.Minute}

	// AuthChangePassword 修改密码：每人每分钟 5 次（规则 6，allauth: change_password 5/m/user）。
	AuthChangePassword = Decl{Name: "auth_change_password", Kind: PerUser, N: 5, Window: time.Minute}

	// AuthReauthenticate 重新认证：每人每分钟 10 次（规则 6，allauth: reauthenticate 10/m/user）。
	AuthReauthenticate = Decl{Name: "auth_reauthenticate", Kind: PerUser, N: 10, Window: time.Minute}

	// AuthManageEmail 改邮箱发码/核验：每人每分钟 10 次（规则 6，allauth: manage_email 10/m/user）。
	AuthManageEmail = Decl{Name: "auth_manage_email", Kind: PerUser, N: 10, Window: time.Minute}

	// AccountDeleteTry 注销时重输密码尝试：每人每小时 5 次（规则 28/223）。
	AccountDeleteTry = Decl{Name: "account_delete_try", Kind: PerUser, N: 5, Window: time.Hour}

	// TeamApply 申请入队：每人每天 20 次（附录 C「业务操作限流」）
	TeamApply = Decl{Name: "team_apply", Kind: PerUser, N: 20, Window: 24 * time.Hour}

	// TeamCreate 创建战队：每人每天 3 次（附录 C；现行站只数表单填对了的那几次，
	// 新栈在服务层同样只对「通过了校验的」计数——M5 落地时接）
	TeamCreate = Decl{Name: "team_create", Kind: PerUser, N: 3, Window: 24 * time.Hour}

	// CommentCreate 发表/编辑评论：每人每分钟 3 条 + 每天 100 条（附录 C、设计 5.6）
	CommentCreateMinute = Decl{Name: "comment_create_minute", Kind: PerUser, N: 3, Window: time.Minute}
	CommentCreateDaily  = Decl{Name: "comment_create_daily", Kind: PerUser, N: 100, Window: 24 * time.Hour}

	// CommentVote 评论点赞/取消：每人每分钟 60 次（附录 C）
	CommentVote = Decl{Name: "comment_vote", Kind: PerUser, N: 60, Window: time.Minute}

	// Search 站内搜索：每个 IP 每分钟 30 次（附录 C、设计 13.16）
	Search = Decl{Name: "search", Kind: PerIP, N: 30, Window: time.Minute}

	// AccountExport 导出个人信息：每人每小时 5 次（设计 3.8）
	AccountExport = Decl{Name: "account_export", Kind: PerUser, N: 5, Window: time.Hour}

	// CalendarFeed 日历订阅地址：每个 IP 每分钟 30 次（规则 216）
	CalendarFeed = Decl{Name: "calendar_feed", Kind: PerIP, N: 30, Window: time.Minute}

	// Unsubscribe 退订链接（页面查看和一键退订）：每个 IP 每分钟 30 次。
	// 现行站没限；链接是签名的、不可猜，这一条只挡拿它试探的脚本。
	Unsubscribe = Decl{Name: "unsubscribe", Kind: PerIP, N: 30, Window: time.Minute}

	// AvatarUpload 上传头像：每人每天 5 次（规则 221）
	AvatarUpload = Decl{Name: "avatar_upload", Kind: PerUser, N: 5, Window: 24 * time.Hour}
)
