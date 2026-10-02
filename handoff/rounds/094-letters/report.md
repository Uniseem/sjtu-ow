# 094 实现报告

## 结论

完成。网站发出的每一种邮件都写成一封信：主题「事情：对象」，「昵称，你好：」，先说结论，信息表，说明，最多一个按钮（下面附原始链接），「祝好！」、落款和日期，页脚说明为什么收到。纯文本和 HTML 两版内容一致；HTML 是深色页头加橙线的白卡片，全部内联样式、不放图片。能进后台的人在 `/_styleguide/emails/` 能看到全部 24 种邮件的样张。

## 逐条结果

1. **设计**：design v5.4，新增 10.3「邮件格式」（每一部分的规则、语气、HTML 外壳、预览文字、主题一览），10.1 指过去，附录 D 记一行
2. **`core/letters.py`**（新）：`Letter`（主题、结论、说明、信息表、列表、验证码、按钮、小字、为什么收到）；`text_of()` / `html_of()` / `render()`；`send()` 一个地址一封，按昵称称呼，裸地址也按邮箱查昵称，查不到写「你好：」；`frame()` 是所有邮件共用的称呼、结尾、落款、日期、页脚；`wrap_text()` 给只有纯文本的邮件（Wagtail 通知）套外壳，纯文本「——」以下挪进页脚
3. **HTML 模板**（新）：`templates/email/layout.html`（外壳：隐藏的预览文字、深色页头、白卡片、页脚；`color-scheme: light`）、`letter.html`、`plain.html`、`parts/facts.html`、`parts/code.html`（验证码 32px 大字）、`parts/button.html`（深红按钮 + 原始链接）
4. **业务邮件**：`teams`、`tournaments`（两个文件）、`scrims`、`moderation` 的 `notifications.py` 全部改写，每种邮件拆成 `*_letter`（只生成内容）和发送函数；主题都带上对象，见设计 10.3 主题一览。原来的「一人一封」「临时队伍成员有效才收信」「内战邮件发送失败不报错」都保留
5. **`core.mail`**：自动生成 HTML 改用 `wrap_text()`；后台「SMTP 测试邮件」改成一封信（`test_letter()`），仍然同步发送、不走队列
6. **allauth**：`AccountAdapter.render_mail()` 给模板加上同一套称呼、结尾、落款、日期和验证码有效分钟数（从设置里读）；找回密码时 allauth 不带用户，按收件邮箱查昵称。改写验证码、找回密码、「这个邮箱还没有注册」、「这个邮箱已经注册过」（新覆盖，原来用的是 allauth 自带的英文模板翻译）、「登录邮箱已更改」（目前没开，顺带统一）的纯文本和 HTML
7. **Wagtail 通知**：覆盖 `wagtailadmin/notifications/base.txt`，称呼、「祝好！」、落款和日期是我们的，页脚说明为什么收到；正文和主题仍是 Wagtail 自带的翻译
8. **邮件样张**：`core/email_samples.py` 用假对象调各个 `*_letter`，渲染全部 24 种；`/_styleguide/emails/` 列表页（每封一个框、纯文本折叠在下面）和 `/_styleguide/emails/<key>/` 单封 HTML（单独的安全策略允许内联样式、只许本站框起来）；权限和样张页一样；样式 `c-mailframe`、`c-mailtext`
9. **测试的例外**：「模板不许写内联样式」的测试放过 `templates/email/` 和套用邮件外壳的 allauth 模板，另加一条测试确认例外只放过这些
10. **测试**：新文件 `core/tests/test_letters.py`（81 条：23 个主题、24 封逐封查信的格式、24 封逐封查 HTML、称呼、顺序、验证码、发送、真实的找回密码流程、没注册的邮箱、纯文本套外壳、Wagtail、样张页两条），`test_templates.py` 加 1 条；旧测试里写死的邮件主题按新主题改（`test_adhoc_teams`、`test_registration`、`test_registration_mode`、`test_state_table`）

## 验收输出

整组检查（Windows 本机，`PYTHONUTF8=1`）：

```
All checks passed!
265 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1191 passed in 203.78s (0:03:23)
No changes detected
System check identified no issues (0 silenced).
```

（1191 = 093 的 1109 + 82。前一次全量跑是 `1 failed, 1189 passed`，失败的是「模板不许写内联样式」，加了邮件模板的例外和对应测试后重跑，就是上面的结果。）

变异（`handoff/rounds/094-letters/mutate.py`，先跑基线）：

```
baseline green, 15 tests
caught another closing -> test_every_email_reads_as_a_letter[entered]
caught nobody greeted by name -> test_someone_we_do_not_know_is_greeted_without_a_name
caught a bare address stays nameless -> test_send_writes_one_letter_per_person_each_by_name
caught a subject without its team -> test_each_subject_says_what_and_about_what[apply]
caught a subject without its tournament -> test_each_subject_says_what_and_about_what[entered]
caught the text forgets why -> test_every_email_reads_as_a_letter[entered]
caught the HTML forgets why -> test_every_html_is_the_same_letter_in_the_frame[entered]
caught no date under the signature -> test_every_html_is_the_same_letter_in_the_frame[entered]
caught dark mode may invert it -> test_every_html_is_the_same_letter_in_the_frame[verify]
caught details before the facts -> test_the_facts_come_before_the_details_and_the_button_after
caught a small code -> test_a_code_is_shown_large_on_its_own
caught the reset code comes nameless -> test_a_password_reset_code_arrives_as_a_letter
caught the reset code in plain paragraphs -> test_a_password_reset_code_arrives_as_a_letter
caught Wagtail greets in its own words -> test_wagtail_notifications_greet_and_close_like_ours
caught text-only mail says goodbye twice -> test_text_only_mail_is_framed_once_with_its_own_footer
caught anyone sees the specimens -> test_the_email_specimens_are_for_admins_only
caught the specimen under the site's policy -> test_an_admin_sees_every_email
caught every template may style inline -> test_only_emails_may_style_inline
restored and green; missed: none
```

18 处变异、18 项检查全部被抓到。

截图：无头 Edge 渲染样张 HTML，760 宽 8 张（你已被报名参加、报名已提交、验证码、入队申请、报名驳回、内战提醒、审核汇总、Wagtail 通知）和 390 宽 1 张，发给了用户。

## 设计偏差

无。

## 未完成 / 顺带发现 / 需要确认

- **未验证**：真邮箱客户端里的样子（截图是浏览器渲染的）；样张页本身没截图（要登录后台，只有测试覆盖）
- **需要确认**：Wagtail 投稿通知的正文和主题要不要也改写
- **顺带发现**：Bash 工具的 heredoc 又吃了一次反斜杠（改 `core/mail.py` 时），断言拦住了，改用编辑工具（AGENTS 里已有）
- **顺带发现**：截图和变异测试同时跑时，截到的可能是正被变异改着的模板，这次发现后等变异结束重截。以后截图避开变异测试

## 改动文件

- 文档：`docs/design.md`、`README.md`、`handoff/STATUS.md`、本目录
- 代码：`core/letters.py`（新）、`core/email_samples.py`（新）、`core/mail.py`、`core/styleguide.py`、`core/urls.py`、`accounts/adapter.py`、`teams/notifications.py`、`tournaments/notifications.py`、`tournaments/notifications_registration.py`、`scrims/notifications.py`、`moderation/notifications.py`
- 模板：`templates/email/`（新：`layout.html`、`letter.html`、`plain.html`、`parts/{facts,code,button}.html`）、`templates/account/email/` 十几个、`templates/wagtailadmin/notifications/base.txt`（新）、`core/templates/core/styleguide_emails.html`（新）
- 样式：`assets/css/input.css`（`c-mailframe`、`c-mailtext`）
- 测试：`core/tests/test_letters.py`（新）、`core/tests/test_templates.py`、`tournaments/tests/{test_adhoc_teams,test_registration,test_registration_mode,test_state_table}.py`
