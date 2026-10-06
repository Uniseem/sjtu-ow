# 210 全站代码与功能复核（报告）

## 做了什么

1. 在测试机上跑整组检查和三条浏览器旅程做基线（下面是真实输出）
2. 七个独立的复核代理只读通读七块代码、测试和设计章节，各交一份「发现 / 查过没问题 / 没来得及看」；结论汇总在 `review.md`
3. 把 181 的 `mutate_guards.py` 复制到本目录、应用清单加上 `backoffice`，在测试机上单独开工作树后台跑守卫普查（不占 `remote-check.sh` 的锁）
4. 用户 10-06 说额度不够、先写文档：**代理的发现没有在测试机上逐条重现**，`review.md` 里标了哪些是我自己核对过代码或源码的；守卫普查的结果还没取回

没改网站代码，没改设计。本轮新增的文件只有本目录四份（`request.md`、`report.md`、`review.md`、`mutate_guards.py`）。

## 基线：整组检查（测试机，2026-10-06 16:49 北京时间）

```
日志：sjtu-ow-test:/srv/sjtu-ow-check/runs/20261006-164906-de5387a.log
测试机 kvm17243： 604c07c 209: 用户协议、隐私政策和用户商量后定稿发布；首页大字改回两行中文（设计 v7.13） + 工作区改动

== ruff (08:49:32)
All checks passed!
403 files already formatted

== Tailwind (08:49:32)
Built production stylesheet '/srv/sjtu-ow-check/repo/static/css/app.css'.

== pytest (08:49:34)
1904 条测试分成 4 片
分片 1：476 passed in 70.98s (0:01:10)
分片 2：476 passed in 80.81s (0:01:20)
分片 3：476 passed in 76.03s (0:01:16)
分片 4：476 passed in 71.00s (0:01:10)

== 迁移 (08:51:01)
No changes detected

== 生产配置 (08:51:02)
System check identified no issues (0 silenced).

== 错误页和模板一致 (08:51:04)

== Docker 镜像 (08:51:05)
构建成功：e5e559d4e3b5

== 全部通过 (08:51:05)
exit=0
```

GitHub CI：`gh run list` 最近 5 次（205–209）全部 `completed success`。

## 基线：三条浏览器旅程（测试机）

```
=== journey            日志：/srv/sjtu-ow-check/runs/20261006-165346-8a4d453.log
ok  浏览器没有报错
全部走通
exit=0
=== journey pages      日志：/srv/sjtu-ow-check/runs/20261006-165535-62783b1.log
全部走通
exit=0
=== journey admin
ok  浏览器没有报错
全部走通
exit=0
```

## 守卫普查（还没取回结果）

```
$ .venv/bin/python handoff/rounds/210-full-review/mutate_guards.py --list | tail -1
共 299 个守卫
     69 core
     54 tournaments
     40 teams
     34 accounts
     30 scrims
     26 backoffice
     19 comments
     10 content
      7 members
      6 moderation
      3 sjtu_ow
      1 search
$ … --soft --list | tail -1
共 37 个守卫
```

179 时是 254 个硬守卫；多出来的 45 个里 26 个是 196 新写的 `backoffice`，其余是 180–209 加的。

在测试机上这样跑的（工作树 `/srv/sjtu-ow-check/sweep`，从快照 `62783b1` 检出，`uv sync --frozen`，`app.css` 从 `repo/` 拷过来）：

```
setsid nohup .venv/bin/python handoff/rounds/210-full-review/mutate_guards.py \
  --workers 3 --copies /srv/sjtu-ow-check/sweep-copies \
  --out handoff/rounds/210-full-review/results.jsonl > handoff/rounds/210-full-review/sweep-log.txt 2>&1 &
```

截稿时（17:10）在跑基线（3 份副本各跑一遍全量），`load average: 3.05`。**取回结果**：`scp sjtu-ow-test:/srv/sjtu-ow-check/sweep/handoff/rounds/210-full-review/{results.jsonl,sweep-log.txt} handoff/rounds/210-full-review/`，看 `sweep-log.txt` 末尾的汇总；每个「全量测试也没抓到」的守卫照 179 报告的表格逐个判断。跑完后删 `/srv/sjtu-ow-check/sweep` 工作树（`git -C /srv/sjtu-ow-check/repo worktree remove --force /srv/sjtu-ow-check/sweep`）和 `/srv/sjtu-ow-check/sweep-copies`。

## 代理复核的覆盖

| 块 | 读了什么 | 发现 |
|---|---|---|
| 账号、成员、搜索 | `accounts/`、`members/`、`search/`、`core/autosave.py`、`core/ratelimit.py`、`core/calendar_feed.py`、设置里的 allauth 配置，以及 `.venv` 里 Django 6 / allauth / Pillow 的源码 | 13 条（2 中） |
| 战队、赛事 | `teams/`、`tournaments/`（含 `registration.py` 全文、`teams_admin.py`、`review_admin.py`）、`backoffice/views/events.py`、`core/outbox.py`、`core/held_views.py`、`core/tasks.py` | 9 条（2 中） |
| 内战、评论 | `scrims/`（含 `teaming.py`、`split_admin.py`）、`comments/`、`static/js/scrim-split.js`、`core/agenda.py` | 11 条（2 中） |
| 核心、运维 | `sjtu_ow/settings/`、`core/` 的 24 个模块、管理命令、`deploy/*`、`Dockerfile`、`scripts/check.sh`、CI，以及 `django_tasks_db` 和 Django 的源码 | 11 条（4 中） |
| 前端 | 12 个 JS 文件、全部模板、templatetags、`core/slots.py`、`content/markdown.py` 的调用点 | 10 条（2 中）；没有 XSS、CSRF |
| 后台 | `backoffice/` 全部、`core/announce_admin.py`、发信页、`core/forms.py`、相关测试和 196/202/205/206 的变异清单 | 11 条（3 中）；权限核对表全部一致 |
| 内容、AI 审核 | **截稿时没回来** | — |

## 顺带发现

- 181 的 `mutate_guards.py` 的应用清单没有 `backoffice`（196 才建的应用），以后复制这个脚本记得看 `APPS`
- 守卫普查的 `--list` 不需要测试库，几秒出结果，适合先看一眼新一轮加了多少守卫

## 验收对照

| 要求 | 结果 |
|---|---|
| 基线整组检查和三条旅程的真实输出 | 上面 |
| `review.md` 每条「确认」有重现证据或读通的代码路径 | 只有读通的代码路径（标「已核对」的我自己读过），**没有在测试机上重现**——用户要求先写文档 |
| `STATUS.md` 更新 | 已更新，「下次开工的第一件事」改成取回普查结果、补内容复核、按 `review.md` 末尾的顺序修 |
