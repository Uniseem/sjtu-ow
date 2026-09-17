# 044 实现报告

## 结论

**部分完成，按 request 预定的范围。** CI 补上了 Tailwind 编译；`/healthz` 两条测试失败时会打印完整响应；磁盘阈值补了边界测试；设计 17.5、17.6 按用户决定改了。**`/healthz` 503 的原因要等这次推送后的 CI 输出**，修复放 045。

## CI 为什么是红的

042、043 两次推送的 CI 都是同样的 3 条（043 那次 run 35241405007）：

```
FAILED core/tests/test_chapter15_audit.py::test_the_homepage_stays_under_the_weight_budget - AssertionError: 首页引用了 css/app.css，但在静态文件里找不到它
FAILED core/tests/test_pages.py::test_healthz_returns_200 - assert 503 == 200
FAILED core/tests/test_pages.py::test_healthz_returns_200_when_database_is_busy - assert 503 == 200
============= 3 failed, 653 passed in 114.66s (0:01:54) ===================
```

**这个仓库以前从没在 GitHub 上跑过 CI。** 42 轮报告里的「CI 全绿」全是本地跑的同一组命令。本地和 CI 机器不一样的地方，本地验证永远发现不了。

### app.css

`static/css/app.css` 是 Tailwind 编译产物，gitignore 了。`Dockerfile` 里编译了，CI 的测试步骤前没有。023 轮的首页体积测试**故意**在找不到资源时失败（之前的版本会跳过 404，于是只测了 HTML 体积）——**测试是对的，CI 少了一步**。

修法：CI 在测试前跑 `tailwind download_cli` 和 `tailwind build`，和 `Dockerfile` 一样。

### /healthz 503

CI 输出只有 `assert 503 == 200` 和一行 `Service Unavailable: /healthz`，**看不出是四项检查里的哪一项**。

排查过的：

- **时区**：心跳写的是 `timezone.now().isoformat()`，带时区的 UTC，机器时区不影响。排除
- **磁盘**：本地 `check_disk()` 返回 `(True, 'free space 28.9%')`。GitHub 托管机器的磁盘通常比较满，**最可能是它**，但没有证据
- **数据库探活、积压任务**：本地测试库是全新的，CI 也是，看不出差别

CI 只能靠推送到 `main` 触发，**没有办法不推送就拿到输出**。所以这轮让两条测试失败时打印完整的 JSON 响应，推送后看是哪一项。

**没做的**：把测试里的磁盘阈值调成 0 让它变绿。如果原因其实不是磁盘，这样做会让 CI 变绿，同时把真问题藏起来。

## 磁盘阈值原来没有测试

找原因时顺便发现：`check_disk` 的 20% 阈值**没有任何测试**。唯一断言磁盘的是 `test_healthz_returns_200` 里的 `disk.ok is True`，结果取决于跑测试那台机器还剩多少空间。

设计 16.6：「磁盘剩余空间大于 20%」。补了：

- 边界测试：剩 21% 通过，**正好 20% 不通过**，19% 不通过（假的 `disk_usage`）
- 剩 10% 时 `/healthz` 返回 503，`disk.ok` 为 `False`

变异测试：

```
✓ 被抓到 边界 <= 改成 < | 1 failed, 9 passed in 0.56s ['FAILED core/tests/test_pages.py::test_disk_check_needs_more_than_twenty_percent_free[20-False]']
✓ 被抓到 拆掉磁盘检查 | 3 failed, 7 passed in 0.50s ['FAILED core/tests/test_pages.py::test_healthz_returns_503_when_disk_is_nearly_full', 'FAILED core/tests/test_pages.py::test_disk_check_needs_more_than_twenty_percent_free[20-False]', 'FAILED core/tests/test_pages.py::test_disk_check_needs_more_than_twenty_percent_free[19-False]']
已还原: True
```

## main 分支

用户决定：「不保护 main，直接推送」。

查 GitHub 分支保护接口时发现，**私有仓库在免费账号下本来就开不了**：

```
{"message":"Upgrade to GitHub Pro or make this repository public to enable this feature.", ... "status":"403"}
```

设计 17.5 从「`main` 受保护、合并请求、至少 1 人审阅」改成「不开分支保护、直接提交推送、推送前本地跑同样的检查、一轮一个提交」；17.6 里两处「合并请求」改成「提交」。附录 D 记 v1.5.9。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
211 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python -m pytest -q
660 passed in 48.92s
```

656 → 660：新增 3 个参数化的边界测试和 1 个 `/healthz` 磁盘满测试。

**推送后的 CI 结果不在这份报告里**：报告随提交一起推送，推送之后才有 CI。结果记在 045。

## 改动文件

```
.github/workflows/ci.yml                     测试前编译 Tailwind
core/tests/test_pages.py                     失败时打印响应；磁盘阈值 4 个测试
docs/design.md                               17.5、17.6、附录 D
AGENTS.md                                    直接推送；本地全绿不等于 CI 全绿
README.md                                    CI 一节加 Tailwind 编译
handoff/STATUS.md
handoff/rounds/043-agents-and-docs/report.md 加推送结果的更正说明
handoff/rounds/044-ci-and-main-policy/       本轮三份
```
