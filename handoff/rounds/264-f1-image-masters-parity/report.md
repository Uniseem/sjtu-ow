# 264 实现报告

## 结论

完成。旧图能过新管线做成母版了（`sjtuow import-media`）；对拍工具（`e2e/parity/`）立起来并跑出了基线：**48 个「地址 × 身份」里只有 `/_styleguide/` 一行通过**。

## 逐条结果

| 编号 | 结果 |
|---|---|
| T1 旧图母版 | `media/import.go` 的 `ImportLegacyMasters`；`media.go` 拆出 `encodeMaster`、`writeMaster`，`Upload` 和导入共用，编码完就放开信号量；`sjtuow import-media <旧站媒体目录>`：打印做成、跳过、找不到、失败各几张并逐条列出，有失败退出码 1 |
| T2 测试会话 | `sjtuow session <邮箱>`：`auth.Store.Create` 发会话，打印令牌 |
| T3 对拍 | `e2e/parity/parity.py` + `run.sh`：旧站用 `scripts/screens.py` 的种子（外加整队赛报名单编号），新站 `migrate` → `import` → `import-media` → `session`；Go + SSR 生产构建 + `caddy:2.10-alpine`（`deploy/Caddyfile.new`）；Chromium 走 DevTools，48 行；`report.md`、`results.json`、截图 |
| T4 基线 | 见下；全文在本轮目录 `parity-baseline.md`，四张样例截图（缩小的 JPEG）在 `shots/` |

## 验收输出

### Go

`go vet ./...`、`staticcheck`、`go test -count=1 ./internal/platform/media/`，日志 `20261010-151417-e88a403`：

```
gofmt: []
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/media	0.501s
```

### 整组

`bash scripts/remote-check.sh`，日志 `20261010-152045-f7ec035`，退出码 0：

```
      Tests  15 passed (15)
      Tests  55 passed (55)
BUDGET-OK
== 全部通过 (07:21:21)
```

### 变异

日志 `20261010-152125-409a48b`，退出码 0：

```
基线全绿
抓到 越出媒体目录的文件名也照读（退出码 1）
抓到 找不到原图当成做好了（退出码 1）
抓到 已有母版不跳过（退出码 1）
抓到 坏文件不报（退出码 1）
4 处全抓到，已改回
```

### 对拍基线

`bash scripts/remote-check.sh run bash e2e/parity/run.sh`，日志 `20261010-151631-f8f23a3`（第一次 `20261010-151445-f7cf116` 在搜索页的中文参数上崩了，见自查第 3 条）：

```
做成母版 1 张，已有跳过 0 张，找不到原图 0 张，失败 0 张。
不同  visitor  /  ← 标题「首页 · SJTU-OW」/「SJTU-OW」；正文不同：-报名中；-截图战队杯；…；像素差 74.95%
不同  visitor  /news/screens-guide/  ← 状态 200 / 404；标题「截图攻略 · SJTU-OW」/「页面不存在 · SJTU-OW」…
不同  visitor  /about/  ← 标题「关于我们 · SJTU-OW」/「关于我们」；正文不同：-用户协议；-隐私政策；…；像素差 98.22%
不同  member   /submit/  ← 状态 302 / 200 …
不同  visitor  /teams/  ← 状态 200 / 500；标题「战队 · SJTU-OW」/「服务器出错 · SJTU-OW」…
不同  visitor  /teams/1/  ← 标题「截图战队 · 战队 · SJTU-OW」/「战队详情 - SJTU-OW」；正文不同：-截图战队；…
…
不同  member   /accounts/password/change/  ← 状态 302 / 200 …
通过  officer  /_styleguide/
PARITY 1/48 通过；报告 /tmp/sjtu-ow-parity/out/report.md，截图 /tmp/sjtu-ow-parity/out/shots
```

（中间省略的 40 行原样在 `parity-baseline.md`。那次跑包含后来删掉的 404 一行，所以是 48 行；现在清单是 47 行。）

## 设计偏差

无。

## 未完成 / 顺带发现 / 需要确认

- **对拍发现**：新站 `/teams/` 是 500（260 的战队列表页拿真数据时组件抛错；263 起服务端不再吞组件错误）。正式站跑的还是旧构建，线上是半页。F6 战队那一组修
- **需要确认**：正式站上跑 `sjtuow import-media`（要部署、要登录服务器），等第 10 节第 1 件
- 后台页面、「能进后台但不是超管」的身份不在对拍里，F8 加

## 改动文件

- `server/internal/platform/media/import.go`（新）、`media.go`、`media_test.go`
- `server/cmd/sjtuow/main.go`（`import-media`、`session`）
- `e2e/parity/parity.py`、`e2e/parity/run.sh`（新）
- `handoff/STATUS.md`、`AGENTS.md`、`handoff/rounds/264-f1-image-masters-parity/`
