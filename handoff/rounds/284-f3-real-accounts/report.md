# 284 实现报告

## 结论

账号真实旅程 35 项与邮件 MIME 解析回归通过；修复 Go 发信顶层 Content-Type 落进正文的问题。三处变异、Go/Web 整组和最终浏览器回归全部通过。全部账号视觉对拍及个人中心完整旅程未验，不标 F3 全量完成。

## 逐条结果

1. 临时空库通过真实浏览器注册用户；验证码经 Go worker→本地 SMTP，读取收件端实际邮件。没有 seed/session/verify-email CLI 绕过账号流程，没有数据库写入账号或验证码。额外设备会话通过真实密码登录接口产生。
2. 35 项覆盖注册两次密码错误保留输入、未验证注册不发会话、未验证密码登录重发码、错码计数与第三次作废、重发冷却、验证登录及欢迎提示一次性消费；退出 GET 仅确认/POST 删除会话、错误登录提示和站内 next；改密码保留本人而撤销其他设备。
3. 邮箱更换需重新认证、错误密码不改状态、草稿回填、新邮箱未验证时旧邮箱保留、错码计数、验证替换及取消待验证邮箱。三步找回密码无凭证不能进新密码页，码错误计数，凭证在 HttpOnly/SameSite Cookie、不在 URL/JS Cookie/浏览器存储；完成撤销所有会话、不自动登录，新密码可登录，旧密码不能登录。
4. 扩展到外部 next 回站内、已注册邮箱同样转验证码页而不登录、未知邮箱找回同样显示验证码页、停用说明、登录码 302、访客保护页 302 和已登录设密码入口 301。
5. 真实 SMTP 暴露 Build 在写完消息头空行后才附 assemble 的 Content-Type；收件端把整段 multipart 当 text/plain，随机边界数字会混进宽松的六码匹配。现在 assemble 仅返回 multipart 正文和类型，Build 将类型写进真正的头，Message.Header 与 SMTP 原始头一致。
6. 新回归从 SMTP Raw 经 net/mail、mime/multipart 读取两种 alternative、related HTML、两张原始 PNG，核对前导零六位码及中文解码。SMTP 收件器只接受测试地址和有效 multipart MIME，只匹配「验证码：」标注，按主题选择找回密码邮件。
7. 最终真浏览器零未捕获异常、CSP 违规、服务器 500。测试服务器和 worker 逐个 TERM，只移本轮临时 Caddy 容器；临时数据库留证据。不改旧站、不引入依赖、不部署正式站。

## 验收输出

全部测试机后台运行，日志在 `/srv/sjtu-ow-check/runs/`，本机对应 `/tmp/sjtuow-284-*.log`。未本机兜底。

- `20261011-150352-c87b4b5`：初版驱动选错导航搜索表单而没有提交注册，退出 1；限定 `#main form` 后继续。
- `20261011-150521-c1d36c7`：宽松邮件提取器下 27 项退出 0。后续揭示非法 MIME 会导致边界随机数字误读，此结果不作为最终合法收信证明。
- `20261011-150730-cf401cc`：扩展旅程在重置验证码失败，退出 1；SMTP 提取值与任务验证码哈希比较不一致，定位真实 MIME 头错位。后面的变异/整组未执行，不记通过。
- `20261011-151135-4ae5660`：修 MIME 后 mail 包测试通过（0.207s）；严格合法 MIME、标注和主题提取后的 `REAL-ACCOUNTS-JOURNEY-OK 35`，零运行时/CSP/500，退出 0。
- `20261011-151305-757bae8`：本轮 mutate.py → scripts/check.sh → run_real_accounts.py → browser-check.mjs，退出 0。三处负向验收 `REAL-ACCOUNT-MUTATIONS-OK 3`（两处命中真实业务断言、一处标准解析器断言）；Go 格式/vet/staticcheck/govulncheck/全部测试/生成物对比通过，Web 15+208，生产构建、预算 96680 字节通过；正常代码再次 `REAL-ACCOUNTS-JOURNEY-OK 35`，原桩浏览器 `COMMENTS-BROWSER-CHECK 23/23` 与 `BROWSER-CHECK-OK`。摘录见 real-checks.txt；两类浏览器证据分别记，不合称真实账号+评论全站验收。

## 设计偏差与限制

无产品设计变化；编码修复恢复设计要求的纯文本/HTML/内嵌图片邮件。HTTP 临时测试站证明 Cookie 的 HttpOnly/SameSite，生产 HTTPS Secure 由现有 Go 回归覆盖；没有冒充真实公网邮箱服务商收信。未重新跑账号四组合截图、不等于所有账号页面验收闭环；个人中心游戏 ID/联系方式在 F5 后续。自查不是独立复核。

## 改动文件

mail/message.go、message_mime_test.go；真实 SMTP/Go/Caddy 测试启动器、CDP 账号旅程、三处变异；12 号文档邮件编码规格、本轮证据和 STATUS。
