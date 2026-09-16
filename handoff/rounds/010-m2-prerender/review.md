# 010 复核结果

> 实现方自查（用户外出）。等用户回来，008–010 可以一起交给 Grok 做独立复核。

## 结论

**通过。** 自查过程中发现并当场修掉 3 个问题（见下），另有 4 条建议留给后续轮次。核心链路——匿名生成、安全闸门、Caddy 静态命中、登录用户一次片段请求、发布 / 改名 / 撤回的实时增删——都在**真的经过 Caddy** 的环境里验证过。

## 验证记录

| 验证 | 方法 | 结果 |
|---|---|---|
| 检查与测试 | `ruff`、`pytest`、`makemigrations --check`、生产 `check --deploy` | 180 passed，其余全干净 |
| 静态命中 | 把 `prerendered/` 挂进 caddy 容器，用仓库里的 Caddyfile | `/` 和文章页 200，`Cache-Control: public, max-age=0, must-revalidate` + ETag；带 `Accept-Encoding: br` 返回 `.br` |
| 路由优先级 | 同上 | `/me/` 和 `?category=guide` 都转给 Django，没有被静态文件截胡 |
| 匿名零请求 | 浏览器经 Caddy 打开 `/news/` | `fragments: 0`，账号区是「登录 注册」，控制台 0 报错 |
| 登录一次请求 | 同一份静态文件，登录后再看 | 只有一次 `/_fragments/state/?slots=account,messages`，账号区变成昵称，骨架类被移除 |
| 实时页不重复请求 | 登录状态打开 `/me/` | `filled: "1"`，`fragments: 0` |
| 事件链路 | worker 真跑：发布 → 改 slug → 撤回 | 生成 33s（30s 合并窗口）、旧地址 3s 删除、新地址 30s 生成、撤回 3s 删除 |
| 安全 | `grep -rl "csrfmiddlewaretoken\|sessionid\|@example.com" prerendered/` + 自动化扫描 | 无命中；测试里还检查了「退出」这类登录态字样 |
| 开关 | `PRERENDER_ENABLED=False` | 请求、删除、全量三个入口都直接返回，磁盘不动 |

## 自查中发现并已修掉

- **A1 生成器自己把自己又排了一次队**：`render_html()` 用 `django.test.Client` 打自己的视图，这个请求同样会走 `PrerenderMissMiddleware`，而此时文件还没写出来，于是又排了一个重复任务。改成生成时带 `X-Prerender: 1` 头，中间件看到就跳过。加了测试：生成完 `requested_at` 必须是空的。
- **A2 中文 slug 会被兜底逻辑漏掉**：`looks_prerenderable()` 原来是 ASCII 白名单，而 Wagtail 允许中文 slug——信号触发的生成能写出文件，兜底中间件却认不出这个路径。改成只挡控制字符、反斜杠、`..` 和 `//`。
- **A3 撤回 / 改名后留下「生成失败」记录**：排队中的旧任务跑到时页面已经 404，于是留下一条 failed 记录让管理员以为出了故障。改成 404 / 410 直接删记录和文件（设计 13.13.4 已补）。

## 建议修（留给后续轮次）

- **B1** allauth 的限流仍然用 `REMOTE_ADDR`，在 Caddy 后面会把所有访客算成同一个 IP。本轮新增的片段接口限流已经按 `X-Forwarded-For` 最后一段取 IP，上线前应该统一，并明确只信任自己的反向代理。
- **B2** 安全闸门是「正文里出现 `csrf_token` / `sessionid` 就拒绝」。一篇讲 CSRF 的技术文章会因此无法预渲染（会回落到实时渲染，不会出错，但管理员会看到一条失败记录）。可以把判断收窄到 `name="csrfmiddlewaretoken"` 这类真实标记。
- **B3** 预渲染目录只在「全量生成」时清理不再存在的页面。可以再加一个每天的孤儿文件清理，或者在清理任务里顺带做。
- **B4** 赛事 / 战队 / 内战 / 组队大厅的预渲染和占位区域要等各自里程碑接入；`page_targets()` 和 `STATE_SLOTS` 都留好了口子。

## 认可的判断

- 用 `django.test.Client` 以匿名身份渲染：走的是线上同一套中间件和视图，比自己拼 `RequestFactory` 更接近真实响应，也能天然拿到 `Set-Cookie` 做安全闸门。
- 三道安全闸门（Set-Cookie / 正文标记 / 状态码与类型）+ 自动化扫描：设计 13.13.5 的要求落到了可执行的检查上。
- 实时渲染页用 `data-state-filled` 跳过片段请求：省掉 `/me/` 这类页面每次一发的无意义请求，静态文件里这个值永远是 `0`，不影响预渲染链路。
- 占位区域清单放服务端、页面自动上报 `data-slot`：模板可以先留位，后面里程碑加一行就能接上。

## 文档更新

`docs/design.md` 更新到 **v1.5.6**：13.13.3（占位清单、`ow_flash` 时机、实时页跳过）、13.13.4（404 / 410 直接删）、附录 C（限流取 IP 的方式），以及 009 遗留的 13.12.2「被替换的字体分片延迟一天删除」。README 新增「半静态渲染」一节（开关、命令、cron、从备份恢复后必须清空）。
