# 043 实现报告

## 结论

**完成，推送还没做**（原因见最后）。新建了 `AGENTS.md`，写明了每份文档管什么、什么时候更新；修掉了三份文档里互相矛盾的进度描述。**核对设计时发现 4 处要求没实现**，记进了 `STATUS.md`。

## 文档原来是怎么维护的，问题在哪

**实际做法**（008 起）：每轮写 `request` / `report` / `review` 三份，轮末更新 `STATUS.md`，提交一次。这套本身在转，42 轮都有完整记录。

**问题是没写明「一件事写在哪」**，于是进度被写进了三个地方，而且只有一个在更新：

| 位置 | 写的 | 实际 |
|---|---|---|
| `README.md` 第一段 | 当前里程碑是 M5 | M0–M6 完成，M7 进行中 |
| `docs/design.md` 头部 | 设计评审中，尚未开始开发 | 同上 |
| `handoff/STATUS.md` | M7 剩余项里有「备份加密与异地同步」；「待定问题」一节写着「不影响 M0」 | 031 轮已做完；早就过了 M0 |

`handoff/README.md` 描述的还是 001–007 的「Grok 实现、Claude 复核」，和 008 起的实际做法不一样。`README.md` 的分队一节还是 021 的下拉，没跟上 032 的拖拽。

## 改了什么

**新规则：一件事只写在一个地方，其他地方指过去。** 进度只写 `STATUS.md`，设计只写 `design.md`，用法只写 `README.md`。

| 文件 | 改动 |
|---|---|
| `AGENTS.md` | 新建。先读什么（按顺序）、目录、常用命令（和 CI 一致）、9 条硬规则、10 条已知的坑（每条注了出处轮次）、**文档维护表** |
| `CLAUDE.md` | 新建，只有一行 `@AGENTS.md`。Claude Code 读 `CLAUDE.md`，其他助手读 `AGENTS.md`，内容只维护一份 |
| `handoff/README.md` | 重写：分工和连做两种做法、连做的 7 步流程、「历史轮次写完不改，错了加更正说明」、文件格式 |
| `handoff/STATUS.md` | 修过时内容；加正式仓库地址；「下次开工」改成 042 的待办；新增「设计里还没实现的」一节 |
| `README.md` | 第一段不再写进度，改成指向 `STATUS.md` 和 `AGENTS.md`；分队一节改成拖拽 + 缓冲区；测试环境一行标明横幅和 robots 没实现 |
| `docs/design.md` | 头部「状态」改成指向 `STATUS.md`，附录 D 记 v1.5.8。**设计内容没改** |
| `handoff/REVIEW-GUIDE.md` | 标题范围和「数字」一节更新到 043 |
| `rounds/026-m7-config-audit/report.md` | 加「043 轮更正」（见下） |

## 核对设计时发现的

写 `STATUS.md` 的待定问题时，逐条去代码里找设计 19.2 的状态，找出 4 处没实现：

| 设计要求 | 怎么查的 | 结果 |
|---|---|---|
| 16.10 测试环境横幅、`robots.txt` 禁止抓取 | 读 `content/views.py` 的 `robots_txt`；搜模板里的「测试环境」 | `robots_txt` 不区分环境；模板里没有横幅 |
| 19.2-3 两步验证；路由表 `/me/security/` 含两步验证 | 搜 `otp` / `mfa` / `2fa`；看 settings 有没有 `allauth.mfa` | 都没有。`/me/security/` 页面存在 |
| 19.2-6、15 章 账号注销、个人信息导出 | 搜「注销」「导出我的」 | 没有 |
| 19.2-12、附录 C「高风险内容暂缓公开」开关 | 搜「暂缓」；看全站设置字段 | 代码里没有；011 报告明确写了没做、等拍板 |

**第 4 条牵出 026 的漏报**：026 轮说附录 C「全部对得上」，但这一行既没有测试，也不在它的「不适用」清单里。已在 026 报告里加更正。

另外设计 17.5 写的是 `main` 受保护、只能走合并请求；实际每轮直接提交 `main`。仓库上 GitHub 了，要不要开分支保护列给用户定。

19.2 第 4 条（投稿初始分类）核对过：`content/services.py` 的 `INITIAL_CATEGORIES` 和设计建议一致，但设计里没标结案。

## 验收输出

新文档里提到的路径和函数逐个确认存在：

```
ok static/css/error.css
ok deploy/error_pages
ok accounts/permissions.py
ok core/dbfile.py
ok tournaments/registration.py
ok scrims/teaming.py
ok handoff/rounds/042-guard-sweep/mutate_guards.py
ok .env.example
ok deploy/crontab.example
core/dbfile.py:13:def database_path() -> Path:
accounts/permissions.py:15:def can_use(user, feature: str) -> bool:
```

`AGENTS.md` 里的 10 个管理命令（`run_worker`、`init_site`、`render_error_pages`、`prerender`、`backup`、`restore`、`cleanup_old_data`、`cleanup_static`、`optimize_db`、`moderate_scan`）逐个找到了命令文件。

```
$ ruff check . && ruff format --check .
All checks passed!
211 files already formatted
```

`ruff format` 的数量从 209 变成 211：新版 ruff 也检查 Markdown 里的代码块，多出来的两个是 `AGENTS.md` 和 `CLAUDE.md`。`ruff check --show-files` 仍是 207 个。

pytest 没重跑：没有改代码和测试。

## 推送

**本地已提交，没推上去。** 这轮之前刚把提交作者从个人身份改成了 `Uniseem`（用户要求），改写历史后提交哈希全变了，远程还是旧的，所以需要强制推送。强制推送被自动模式的权限检查拦下了，要用户批准或自己执行。

> **044 轮更正**：用户说「直接推送」后强制推送成功（`7ec6a2a...2ae2385 main -> main (forced update)`），GitHub 上 42 个提交的作者都是 Uniseem。推送后发现 CI 是红的，见 044。

## 改动文件

```
AGENTS.md                                    新建
CLAUDE.md                                    新建
README.md
docs/design.md
handoff/README.md
handoff/STATUS.md
handoff/REVIEW-GUIDE.md
handoff/rounds/026-m7-config-audit/report.md 加更正说明
handoff/rounds/043-agents-and-docs/          本轮三份
```
