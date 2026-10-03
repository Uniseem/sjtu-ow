# 120 演示站接上域名，限流按真实访客 IP（报告）

## 查到的

- 域名解析：`sjtu.ow-shanghaiuniversity.com` → `sjtu-ow-wesite-china-mainland-full-optimized.anylocate.cc` → `189.24.110.12`（用户的反向代理）
- 反代连到本机的来源（`tcpdump` 抓 22887 的 SYN）：`CloudflareWARP In IP 100.96.0.7 > 100.96.0.10.22887`
- 改之前，本机带不同 Host 请求：

```
sjtu.ow-shanghaiuniversity.com /members/5/ -> 400
sjtu.ow-shanghaiuniversity.com /admin/login/ -> 400
sjtu.ow-shanghaiuniversity.com / -> 200
sjtu.ow-shanghaiuniversity.com /members/ -> 200
169.58.217.180 /members/5/ -> 200
169.58.217.180 /admin/login/ -> 200
```

  `.env` 当时是 `DJANGO_ALLOWED_HOSTS=169.58.217.180,localhost`。`/` 和 `/members/` 是预渲染页，Caddy 直接发，不经过 Django，所以不受影响

- 写测试时又发现：登录、注册、改密码等页面共用的 `account/_form.html` 不显示整体错误，密码输错只是刷新页面，「邮箱或密码不正确」「登录失败次数过多」都看不到（个人中心的联系方式、游戏 ID 页各自补过，所以那两页有）

## 做了什么

1. **演示站配置**（服务器上，改前备份 `.env.bak-120`、`Caddyfile.vps.bak-120`）：
   - `.env`：`DJANGO_ALLOWED_HOSTS=sjtu.ow-shanghaiuniversity.com,169.58.217.180,localhost`，`SITE_URL=https://sjtu.ow-shanghaiuniversity.com`，`DJANGO_CSRF_TRUSTED_ORIGINS=https://sjtu.ow-shanghaiuniversity.com,http://169.58.217.180:22887`（权限仍是 600）
   - `Caddyfile.vps`：`trusted_proxies static private_ranges 100.96.0.0/12`、`trusted_proxies_strict`；之后按 AGENTS 的做法从新的仓库 Caddyfile 重新生成（`diff` 只差这一块）
   - 同步 Wagtail 站点地址（`sjtu.ow-shanghaiuniversity.com:443`），全量预渲染
2. **访客 IP 由 Caddy 定**：`deploy/Caddyfile` 新片段 `(django)`，`reverse_proxy web:8000` 带 `header_up X-Real-IP {client_ip}`，四处转发都改成 `import django`；`core.ratelimit.client_ip()` 只认 `X-Real-IP`，没有时用 `REMOTE_ADDR`（不再取 `X-Forwarded-For` 最后一段）；`AccountAdapter.get_client_ip` 用同一个函数，allauth 的登录、注册限流不再全站共用一个计数。`web` 只在 Compose 内网 `expose`，访客碰不到，`X-Real-IP` 只可能来自 Caddy
3. **整体错误**：`account/_form.html` 最前面显示 `form.non_field_errors`；联系方式、游戏 ID 两页去掉各自的那份，免得显示两次
4. **文档**：设计 v6.16（16.9「前面再加一层反向代理时」、附录 C 的限流说明）；README（反代时怎么配、症状对照）；AGENTS（测试机不再有域名；第二台的域名、反代路径、`.env`、`Caddyfile.vps` 的生成方式）

## 命令输出

改之后经域名访问（在服务器上 `curl https://sjtu.ow-shanghaiuniversity.com/...`，`/root/verify_domain.sh`）：

```
/                  200 -> 
/members/          200 -> 
/members/5/        200 -> 
/teams/            200 -> 
/search/?q=a       200 -> 
/admin/            302 -> https://sjtu.ow-shanghaiuniversity.com/accounts/login/?next=/admin/
/admin/login/      200 -> 
/accounts/login/   200 -> 
/healthz           200 -> 
--- canonical on a live page
<link rel="canonical" href="https://sjtu.ow-shanghaiuniversity.com/members/5/">
--- login POST with a wrong password (CSRF must pass: expect 200, not 403)
200
邮箱或密码不正确。
```

限流记下的访客地址（数据库缓存里搜索限流的键，带过期时间；当时 `now 2026-10-03 16:41:06 UTC`）：

```
100.96.0.7:29850744 2026-10-03 16:26:36
172.20.0.1:29850760 2026-10-03 16:42:40
169.58.217.180:29850760 2026-10-03 16:45:40
169.58.217.180:29850761 2026-10-03 16:46:04
```

第一行是部署前（按 `X-Forwarded-For` 最后一段取，成了 WARP 的地址），早已过期；之后经域名来的请求记的是访客地址（这里访客是服务器自己，公网 IP `169.58.217.180`）；`172.20.0.1` 是在服务器上直接请求 `127.0.0.1:22887`（Docker 网关）。

变异（`mutate.py`，7 处，第一次全部被抓到）：

```
baseline green, 7 tests
caught the visitor is Caddy again -> test_the_visitor_is_whoever_caddy_names
caught the visitor is Caddy again -> test_the_page_is_rate_limited_per_ip
caught the last X-Forwarded-For entry wins -> test_x_forwarded_for_alone_names_nobody
caught allauth counts everyone together -> test_allauth_asks_the_same_question
caught allauth counts everyone together -> test_failed_logins_count_per_visitor
caught Caddy does not name the visitor -> test_every_route_to_django_names_the_visitor
caught one route bypasses the snippet -> test_every_route_to_django_names_the_visitor
caught the login page hides whole-form errors -> test_failed_logins_count_per_visitor
caught contacts show the error twice -> test_a_whole_form_error_shows_once
restored and green; missed: none
```

改了一条原有测试：搜索按 IP 限流的测试原来用 `X-Forwarded-For` 区分访客，改成 `X-Real-IP`。

整组检查：

```
All checks passed!
294 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
1431 passed in 250.91s (0:04:10)
```

演示站：镜像时间 `2026-10-03 18:39:42 +0200`，`Caddyfile.vps` 验证 `Valid configuration`，全量生成「成功 46，失败 0」。

## 没做 / 未验证

- 测试机（185.99.135.224）没有动：它的 `.env` 里可能还写着这个域名，但域名已经不指向它了；它那边的 Caddy 证书续期会失败，用不到就不管
- 没有从国内网络、手机网络经域名访问测试（只在服务器上 `curl` 过）
- 用户的反代如果以后换了连接方式（不走 WARP），来源地址不在 `100.96.0.0/12` 里，Caddy 又会丢掉 https 信息，要回来改 `Caddyfile.vps`
