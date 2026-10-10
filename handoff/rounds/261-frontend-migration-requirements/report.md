# 261 实现报告

## 结论

完成。写了 `docs/frontend-migration.md`，接进了 `handoff/STATUS.md` 和 `AGENTS.md`。只有文档，没改代码，没动正式站。

## 逐条结果

| 编号 | 结果 |
|---|---|
| T1 正式站核查 | 做了。下面「验收输出」里是原样输出 |
| T2 代码核查 | 做了。数量和位置写进文档第 2.2 节；误报的处理见 `review.md` |
| T3 要求文档 | `docs/frontend-migration.md`，438 行，12 节：结论、依据和优先级、现状（S1–S15 正式站、C1–C14 代码、流程）、保留和重写、不变量 I1–I12、架构要求 A1–A14 和旧部件对照、前台每页验收（6.1–6.6）、后台每页验收、后端和部署缺口 B1–B8、验收方法（每轮必跑、对拍、旅程、完成的定义、进度表）、待拍板六件、阶段计划 F0–F10、流程纪律 |
| T4 接进 STATUS、AGENTS | STATUS：文件头、新的「前台迁移」一节和「前台页面进度」表、「现在该谁动手」加 261、「还没定的」加第 10 节六件、轮次表加 261。AGENTS：开工前读什么、重构一节、新的坑、文档维护表 |

## 验收输出

### 正式站的状态码（访客，2026-10-10 14:07 前后）

```
/                            200 13519
/news/                       200 11791
/teams/                      200 11289
/members/                    200 11032
/tournaments/                200 10445
/scrims/                     200 11288
/about/                      200 9903
/search/?q=a                 200 9885
/accounts/login/             200 10794
/accounts/signup/            200 12396
/accounts/password/reset/    200 9903
/me/                         200 12454
/admin/                      200 4335
/_styleguide/                404 522
/teams/1/                    200 11610
/members/1/                  200 11374
/sitemap.xml                 404 19
/robots.txt                  404 19
/healthz                     503 131
/static/img/favicon.svg      200 238
/favicon.ico                 404 522
```

```
/news/%E7%BD%91%E7%AB%99%E6%AD%A3%E5%BC%8F%E5%8F%91%E5%B8%83/ 404
/news/?category=x                                  200
/tournaments/1/                                    200
/scrims/1/                                         200
/me/teams/                                         200
/teams/999/                                        200
/teams/abc/                                        404
/admin/articles/                                   200
POST unsubscribe 405
```

`/healthz`：

```
{"status":"error","checks":{"database":{"ok":true},"disk":{"ok":false},"task_backlog":{"ok":true},"worker_heartbeat":{"ok":true}}}
```

`/about/` 的正文整个就是：

```
<main id="main" class="flex-1">
<h1>关于我们</h1>
</main>
```

战队接口（页面按顶层读 `team.name`，接口把战队放在 `team` 里）：

```
{"team":{"id":1,"name":"测试战队","description":"123","logo_image_id":null,"is_recruiting":true,"recruiting_roles":["tank","damage","support"],"disbanded_at":"2026-10-04T12:27:27.695804Z",...},"members":[],"alumni":[],"max_members":30,"viewer":{...}}
```

成员墙的链接：

```
<a href="/members/undefined/" class="c-person__name font-semibold hover:text-primary-text block truncate">超级管理员</a>
```

标题：

```
/                  <title>SJTU-OW</title>
/members/          <title>成员 - SJTU-OW</title>
/news/             <title>资讯</title>
/teams/            <title>战队</title>
/scrims/           <title>内战 - SJTU-OW</title>
/accounts/login/   <title>登录 - SJTU-OW</title>
```

内置浏览器里看了 `/teams/1/`（队名空白、问号队标、「暂不招募」「0 人」「暂无队员信息」）和 `/accounts/login/`（没有「忘记密码」），控制台没有报错。

### 代码

```
$ grep -c '^  page(' web/apps/site/src/routes.ts        → 34
$ grep -c '^  dynamicPage(' web/apps/site/src/routes.ts → 15
$ grep -c '^  admin(' web/apps/site/src/routes.ts       → 40
```

Vue 3.5.43 的 `createApp().mount`（`runtime-dom.cjs.js` 1893–1903 行）：

```
    if (container.nodeType === 1) {
      container.textContent = "";
    }
    const proxy = mount(container, false, resolveRootNamespace(container));
```

### 测试机整组

`bash scripts/remote-check.sh`，日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261010-142854-249e71d.log`，退出码 0：

```
No vulnerabilities found.
...
首页壳 gzip：HTML 2770 + CSS 19504 + JS 62261 = 84535 字节（脚本上限 122880，合计上限 307200）
BUDGET-OK

== 全部通过 (06:29:29)
```

## 设计偏差

无（没改设计文档）。文档第 10 节列了需要拍板、拍板后会改 `design-next.md` 或 12 号文档的地方（后台形态、新依赖、对拍阈值、旧地址）。

## 未完成 / 顺带发现 / 需要确认

- **需要确认**：文档第 10 节六件。最急的是第 1 件：正式站要不要趁 48 小时回滚窗口（按快照 `legacy-final-20261009134549` 推算约 10-11 到期）回滚到旧站
- **顺带发现**：`/healthz` 503，磁盘检查不过（S15）。没登录服务器看，清理前要用户点头
- **顺带发现**：`web/apps/site/screenshot-home.png` 被提交进了仓库（C13），留给 F1 清掉
- **顺带发现**：`STATUS.md` 的轮次表停在 238，239–260 只记在「现在该谁动手」里；本轮只补了 261 一行

## 改动文件

- `docs/frontend-migration.md`（新）
- `handoff/STATUS.md`
- `AGENTS.md`
- `handoff/rounds/261-frontend-migration-requirements/`（`request.md`、`report.md`、`review.md`）
