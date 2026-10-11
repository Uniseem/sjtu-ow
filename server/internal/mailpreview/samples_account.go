package mailpreview

import "github.com/Uniseem/sjtu-ow/server/internal/platform/mail"

func accountSamples() []Sample {
	return []Sample{
		specimen("verify", "账号", "注册 / 修改邮箱验证码", "注册人", memberName, "server/internal/accounts/service.go", mail.Letter{
			Subject: "邮箱验证码",
			Lead:    "你正在注册 SJTU-OW，或者给账号换一个邮箱。请在页面上输入下面的验证码：",
			Code:    "482915",
			Note:    "验证码 15 分钟内有效。如果这不是你本人的操作，请忽略这封邮件，不会有任何变化。",
			Reason:  "你收到这封邮件，是因为有人在本站填写了这个邮箱。",
		}),
		specimen("reset", "账号", "找回密码验证码", "本人", memberName, "server/internal/accounts/service.go", mail.Letter{
			Subject: "找回密码验证码",
			Lead:    "你正在重置 SJTU-OW 账号的密码。请在页面上输入下面的验证码：",
			Code:    "730264",
			Note:    "验证码 3 分钟内有效。如果这不是你本人的操作，请忽略这封邮件，你的密码不会改变。",
			Reason:  "你收到这封邮件，是因为有人用这个邮箱申请了找回密码。",
		}),
		specimen("unknown", "账号", "没有注册的邮箱", "填写的邮箱", "", "server/internal/accounts/service.go", mail.Letter{
			Subject:    "这个邮箱还没有注册",
			Lead:       "有人用这个邮箱在 SJTU-OW 申请了账号操作（比如找回密码），但这个邮箱还没有注册过。",
			Paragraphs: []string{"你可以用这个邮箱注册一个新账号。如果不是你本人的操作，请忽略这封邮件。"},
			Action:     []string{"注册账号", sampleURL("/accounts/signup/")},
			Reason:     "你收到这封邮件，是因为有人在找回密码页面填写了此邮箱。",
		}),
		specimen("exists", "账号", "已经注册过的邮箱", "填写的邮箱", "", "server/internal/accounts/service.go", mail.Letter{
			Subject:    "这个邮箱已经注册过",
			Lead:       "有人用这个邮箱（member@example.invalid）在 SJTU-OW 注册，但它已经注册过了，所以没有新建账号。",
			Paragraphs: []string{"如果忘了密码，可以在找回密码页面重置。如果不是你本人的操作，请忽略这封邮件。"},
			Action:     []string{"找回密码", sampleURL("/accounts/password/reset/")},
			Reason:     "你收到这封邮件，是因为有人用此邮箱尝试注册 SJTU-OW。",
		}),
		specimen("verify-resend", "账号", "重新发送邮箱验证码", "未验证成员", memberName, "server/internal/accounts/service.go", mail.Letter{
			Subject: "邮箱验证码", Lead: "你的 SJTU-OW 邮箱验证码如下：", Code: "482915",
			Note:   "验证码 15 分钟内有效。如果这不是你本人的操作，请忽略这封邮件，不会有任何变化。",
			Reason: "你收到这封邮件，是因为有人在 SJTU-OW 申请重新发送邮箱验证码。",
		}),
		specimen("verify-already", "账号", "邮箱已经完成验证", "已验证成员", memberName, "server/internal/accounts/service.go", mail.Letter{
			Subject: "你的邮箱已完成验证",
			Lead:    "有人在 SJTU-OW 尝试为这个邮箱重新发送验证码，但该邮箱此前已经完成了验证，无需再次验证。",
			Action:  []string{"登录账号", sampleURL("/accounts/login/")},
			Note:    "如果你忘记了密码，可以通过找回密码重新设置。如果这不是你本人的操作，请忽略这封邮件，你的账号很安全。",
			Reason:  "你收到这封邮件，是因为有人在 SJTU-OW 尝试重新发送邮箱验证码。",
		}),
		specimen("verify-at-login", "账号", "登录时验证邮箱", "未验证成员", memberName, "server/internal/accounts/service.go", mail.Letter{
			Subject: "邮箱验证码", Lead: "有人用这个邮箱登录 SJTU-OW，但它还没有验证过。请输入下面的验证码完成验证：", Code: "518204",
			Note:   "验证码 15 分钟内有效。如果这不是你本人的操作，请忽略这封邮件，不会有任何变化。",
			Reason: "你收到这封邮件，是因为有人在本站用这个邮箱登录。",
		}),
		specimen("email-change-code", "账号", "更换登录邮箱验证码", "新邮箱", memberName, "server/internal/accounts/service.go", mail.Letter{
			Subject: "验证你的新邮箱",
			Lead:    "你正在更换 SJTU-OW 账号的登录邮箱。请在页面上输入下面的验证码：",
			Code:    "610248",
			Note:    "验证码 15 分钟内有效、最多尝试 3 次。如果这不是你本人的操作，请忽略这封邮件。",
			Reason:  "你收到这封邮件，是因为有人申请将此邮箱绑定为 SJTU-OW 账号。",
		}),
		specimen("email-changed", "账号", "登录邮箱已更换", "原邮箱", memberName, "server/internal/accounts/email_flow.go", mail.Letter{
			Subject:    "你的登录邮箱已更换",
			Lead:       "你的 SJTU-OW 账号登录邮箱已更换。",
			Facts:      [][2]string{{"新邮箱", "new-member@example.invalid"}},
			Paragraphs: []string{"如果不是你本人的操作，请尽快联系管理员。"},
			Reason:     "你收到这封邮件，是因为这是该账号原来的登录邮箱。",
		}),
		specimen("avatar-taken-down", "账号", "头像被撤下", "上传的人", memberName, "server/internal/settings/avatars.go", mail.Letter{
			Subject:    "你的头像已撤下",
			Lead:       "管理员撤下了你上传的头像，网站会使用默认头像。",
			Facts:      [][2]string{{"原因", "色情低俗"}},
			Paragraphs: []string{"你可以上传符合社区规则的新头像。如果有疑问，请联系管理员。"},
			Action:     []string{"打开个人中心", sampleURL("/me/")},
			Reason:     "你收到这封邮件，是因为你在 SJTU-OW 上传过头像。",
		}),
	}
}
