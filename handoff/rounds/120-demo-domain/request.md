# 120 演示站接上域名，限流按真实访客 IP

## 背景

用户（2026-10-04）：「我演示站已经配了反代了，但是呢，有些界面进去会 400，后台好像也是。是因为我反代和部署在不同的 vps 上吗？」截图是 `sjtu.ow-shanghaiuniversity.com/members/5/` 的「Bad Request (400)」。同一条消息里定了复查第五部分：直接处置只做发信、后台配色不换（发信放下一轮做）。

查到的情况（服务器上实际跑过）：

- 域名经 `anylocate.cc`（`189.24.110.12`，用户的反向代理）转到 169.58.217.180:22887，**经 Cloudflare WARP 内网连过来**，来源地址 `100.96.0.7`
- **400 的原因**：`.env` 的 `DJANGO_ALLOWED_HOSTS` 只有 IP（当时还不知道域名）。由 Django 实时生成的页面（成员个人页、后台、登录）带域名访问一律 400；首页、成员列表这些预渲染页由 Caddy 直接发，所以正常
- **和「不在同一台机器」有关的**：`Caddyfile.vps` 只信任内网地址的代理，WARP 的 `100.96.x` 不在里面，反代带来的「访客用的是 https」被 Caddy 丢掉，Django 会以为是明文 http
- **顺带发现的代码问题**：Django 拿到的访客 IP 不对。allauth 的登录、注册限流用 `REMOTE_ADDR`，在 Compose 里永远是 Caddy 容器的地址，**全站所有人共用一个计数**（每分钟 10 次登录失败就会把所有人挡在外面），两台机器都这样；本站自己的限流（页面状态片段、搜索）取 `X-Forwarded-For` 最后一段，前面再有一层反代时就成了反代的地址

## 本轮范围

1. **演示站配置**（服务器上，不进仓库）：`.env` 加域名、`SITE_URL` 和 CSRF 来源改成 `https://域名`；`Caddyfile.vps` 信任 `100.96.0.0/12`（WARP）并用 `trusted_proxies_strict`（访客 IP 取最右边不受信任的地址，伪造的 `X-Forwarded-For` 选不了）；同步 Wagtail 站点地址、全量预渲染
2. **访客 IP 由 Caddy 定**：仓库 `deploy/Caddyfile` 转给 Django 的每一处都带上 `X-Real-IP {client_ip}`（Caddy 按受信任代理算出的访客地址，覆盖请求里自带的同名头）；`core.ratelimit.client_ip()` 认这个头，没有时（本机开发）用 `REMOTE_ADDR`；allauth 的限流通过 `AccountAdapter.get_client_ip` 用同一个函数
3. **文档**：AGENTS（第二台服务器的域名、反代路径、`Caddyfile.vps` 怎么生成；测试机那一节的域名已经不指向它）；设计 16.9（反向代理和访客 IP）、附录 C（限流取哪个 IP）

**不做**：发信处置（121）。

## 验证

测试：`client_ip` 只认 `X-Real-IP`、不认 `X-Forwarded-For`；两个不同 IP 的访客登录失败各算各的；`Caddyfile` 里每处 `reverse_proxy web:8000` 都带这个头。变异逐条改坏。服务器上经域名实测各页、登录提交过 CSRF、两个不同来源 IP 互不影响限流。

## 验收标准

`AGENTS.md`「常用命令」那组全绿；变异全部被抓到；推送 `main`，CI 绿；演示站升级。
