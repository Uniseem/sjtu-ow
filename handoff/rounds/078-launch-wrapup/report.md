# 078 实现报告

## 结论

**完成。** 074–077 留下的几件小事收掉了，上线计划写成了可以照着做的步骤（合并分支、测试机从 066 升级到 078、升级后检查什么）。部署本身没做：这个会话没有测试机的 SSH 密钥。

## 逐条结果

| 任务 | 结果 |
|---|---|
| 1 保留地址片段 | 补上 `search`。写测试时让它从路由表里自己找「Django 在 Wagtail 之前接管的第一段路径」，把路由表打出来一看，还漏了 `registrations`（015 起就有 `/registrations/<id>/`）和 Wagtail 自己的 `_util`；再加上 Caddy 直接提供、根本到不了 Django 的 `static`、`media`。五个都补进 `RESERVED_CHILD_SLUGS`。以后加了新的顶层路由忘了保留，这条测试会红 |
| 2 「重装」→「坦克」 | `TeamApplication.role_tank` 的中文名、`role_labels()`（给队长的邮件里用）、申请表单的勾选框。迁移 `teams/0002` 只改字段说明，`sqlmigrate` 是 `(no-op)`，不动表 |
| 3 手机标签条 | `static/js/app.js`：页面上每个 `c-tabs` 横向放不下时，滚到 `aria-current` 那一项（外部脚本，符合 CSP）。真浏览器验证见下 |
| 4 设计 13.13.3 | 账号区域一行改成现在的样子；顺带 5.4.3 的「投稿入口在导航栏」也是 v2.0 以前的说法，改成实际的五处入口。设计 v2.0.1 |
| 5 REVIEW-GUIDE | 新增「074–078 前台重做」一节：最可能有问题的 7 处（每处写了怎么验）、6 条主观取舍、没验证的 |
| 6 STATUS | 「下次开工的第一件事」改写：分支快进合并到 `main` 的命令、SSH 主机密钥的两种情况、升级命令（备份 → 构建 → 停 → 迁移 → 清旧内容类型 → `init_site` → 起 → 全量预渲染）、删 cron 里的 Webhook 行、升级后 5 项检查 |

## 设计偏差

无。任务 1 比 `request.md` 多保留了四个片段，是同一条规则（设计 13.4「网址片段不能和固定路径冲突」）本来就要求的。

## 真浏览器验证（标签条）

360×800，Chromium，登录一个示例账号，脚本在本会话 scratchpad 的 `tabs.js`：

```
/me/ {"scrollLeft":0,"visible":true,"label":"基本资料"}
/me/scrims/ {"scrollLeft":273,"visible":true,"label":"我的内战"}
/me/security/ {"scrollLeft":273,"visible":true,"label":"账号安全"}
errors []
```

把赋值那一行临时改掉再跑，后两页的当前项看不到了，说明是这行脚本起的作用（跑完已还原）：

```
/me/ {"scrollLeft":0,"visible":true,"label":"基本资料"}
/me/scrims/ {"scrollLeft":0,"visible":false,"label":"我的内战"}
/me/security/ {"scrollLeft":0,"visible":false,"label":"账号安全"}
errors []
```

## 验收输出

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
244 files already formatted

$ uv run python manage.py tailwind build --force
Built production stylesheet '/home/user/sjtu-ow/static/css/app.css'.

$ uv run pytest -q -p no:cacheprovider
948 passed in 240.14s (0:04:00)

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).
exit 0

$ uv run python manage.py render_error_pages   # git status deploy/：无变化
Wrote /home/user/sjtu-ow/deploy/error_pages/maintenance.html

$ uv run python manage.py sqlmigrate teams 0002
BEGIN;
--
-- Alter field role_tank on teamapplication
--
-- (no-op)
COMMIT;
```

945 → 948。第一次跑整组检查时 `ruff format --check` 报了两个测试文件没格式化，格式化后重跑，上面是第二次的结果。Docker 构建未验证。

## 变异

`handoff/rounds/078-launch-wrapup/mutate.py`：

```
KILLED   保留片段漏掉 search  | 1 failed, 7 passed in 3.16s
KILLED   保留片段漏掉 registrations  | 1 failed, 7 passed in 3.33s
KILLED   保留片段漏掉 Caddy 的 static  | 1 failed, 7 passed in 3.29s
KILLED   入队申请表单还叫重装  | 1 failed, 24 passed in 7.22s
KILLED   给队长的邮件还叫重装  | 1 failed, 24 passed in 7.60s
KILLED   标签条不滚到当前项  | 1 failed, 83 passed in 20.68s
KILLED   手机标签条不标当前项  | 1 failed, 83 passed in 21.00s
7/7 killed
```

标签条那条测试只能钉住「模板标了当前项、脚本按当前项滚动」这两头；滚得对不对是排版行为，靠上面的浏览器验证。

## 未完成 / 顺带发现

- **文字对比度不够**：写 REVIEW-GUIDE 时把颜色令牌的对比度算了一遍。第三级文字色 `ink-3`（`#847C7A`）在页面底色 `canvas` 上 3.75:1、在白底上 4.08:1、在凹陷底色 `sunken` 上 3.5:1，都不到 WCAG AA 正文要求的 4.5:1。设计 13.2.3 写的是「只用于 14px 以上的非关键文字」，但 14px 不算 WCAG 的大字号，而且实际用在日期、列表的副行、评论的署名行、「未定级」、日程带的星期、输入框的占位文字、表格的序号上，有些是 12px（状态的实心方块也用它，图形只要 3:1，够）。其他文字色都够（`ink-2` 6.78、`night-ink-2` 在深色上 7.82、红色文字 6.41）。改令牌要先改设计，留给 079
- 部署未做（没有 SSH 密钥）；074–078 的 CI 要等合并到 `main` 才会跑

## 改动文件

```
content/models.py                                 RESERVED_CHILD_SLUGS 加五个
content/tests/test_content.py                     固定路由都要保留
teams/models.py、teams/forms.py                   坦克
teams/migrations/0002_role_tank_label.py          新建（只改字段说明）
teams/tests/test_teams.py                         坦克
static/js/app.js                                  标签条滚到当前项
core/tests/test_design_system.py                  标签条
docs/design.md                                    v2.0.1：13.13.3、5.4.3、附录 D
handoff/REVIEW-GUIDE.md                           074–078
handoff/STATUS.md、handoff/rounds/078-launch-wrapup/
```
