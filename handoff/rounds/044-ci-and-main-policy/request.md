# 044 CI 转绿；记录 main 分支的决定

## 背景

1. **用户 2026-09-17 决定：「不保护 main，直接推送」。** 设计 17.5 写的是 `main` 受保护、只能走合并请求、至少 1 人审阅，17.6 也按合并请求写。设计要改成实际做法
2. **仓库推到 GitHub 后，CI 第一次真正跑起来，结果是红的**（042 那次推送，run 35239563037）：

```
FAILED core/tests/test_chapter15_audit.py::test_the_homepage_stays_under_the_weight_budget - AssertionError: 首页引用了 css/app.css，但在静态文件里找不到它
FAILED core/tests/test_pages.py::test_healthz_returns_200 - assert 503 == 200
FAILED core/tests/test_pages.py::test_healthz_returns_200_when_database_is_busy - assert 503 == 200
================== 3 failed, 653 passed in 138.89s (0:02:18) ===================
```

本地一直是全绿，**CI 从来没在 GitHub 上跑过**，所以这些问题一直没暴露。

## 分析

- **`app.css`**：Tailwind 编译产物，不进仓库。`Dockerfile` 里有 `tailwind download_cli` + `tailwind build`，CI 的测试步骤前面没有。023 轮加的首页体积测试专门要求静态资源必须找得到（防止 404 被跳过），所以在 CI 里红了——**测试是对的，是 CI 少了一步**
- **`/healthz` 503**：CI 只打印了状态码，没打印是哪项检查没过。本地 200。候选：数据盘剩余空间 ≤ 20%（GitHub 托管机器的磁盘很满）、worker 心跳、数据库探活、积压任务。**最可能是磁盘，但没证据**

## 补充发现

查 GitHub 的分支保护接口：

```
{"message":"Upgrade to GitHub Pro or make this repository public to enable this feature.", ... "status":"403"}
```

**私有仓库在免费账号下本来就开不了分支保护。** 用户的决定和平台限制一致。

## 任务

1. 设计 17.5、17.6 改成直接提交推送 `main`，附录 D 记版本；`STATUS.md` 记进「你已经拍板的」；`AGENTS.md` 同步
2. CI 在测试前编译 Tailwind（和 `Dockerfile` 一致）
3. 两条 `/healthz` 测试失败时要打印整个响应
4. `check_disk` 的 20% 阈值目前没有任何测试（只有 `test_pages.py` 断言 `disk.ok is True`，结果取决于跑测试那台机器的磁盘），补边界测试

**明确不做**：`/healthz` 503 的修复。CI 只能靠推送到 `main` 触发（没有 `workflow_dispatch`），要拿到 503 的原因只能先推一次带诊断信息的版本。**没确认原因之前不改阈值、不跳过测试**——那样 CI 会变绿，但如果原因不是磁盘，就把一个真问题藏起来了。拿到原因后在 045 修。

## 验收标准

1. 本地 `ruff` / `pytest` / `makemigrations --check` / 生产 `check --deploy` 干净
2. 推送后 CI 里 `app.css` 那条不再失败；`/healthz` 两条如果还失败，输出里能看到是哪项检查没过
3. `check_disk` 新测试变异确认咬得住
4. git 提交以 `044:` 开头
