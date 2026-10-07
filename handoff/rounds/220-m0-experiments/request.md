# 220 M0 的五个验证实验

## 背景

`docs/rewrite-research/12-architecture.md` 11.2：M0 要先拍板（D1–D4 已在 218 拍板）、改设计 v8.0、做五个小实验，**有一项不行就回到第 12 节重新拍板**。设计 v8.0 要把第 2、13.13、16、17 章重写，工作量大，而五个实验的结果可能改变里面的写法，所以先做实验、后写设计（221）。

五个实验验证的是架构里五个「如果不成立就要换方案」的假设：

| 实验 | 假设（12 号文档的出处） | 不成立的后果 |
|---|---|---|
| E1 薄 SSR + 严格 CSP | Vue 3 的服务端渲染 + 激活，在 `script-src 'self'`、无内联脚本、无 `style` 属性下跑得通；首页壳的体积在预算内（3.5、6.2、6.9） | CSP 要放宽到 nonce（Nuxt 的老路），D1 要重新想 |
| E2 纯 Go 的 WebP 编码 | `github.com/gen2brain/webp`（不用 cgo）编一张 2400×1350 够快（5.13、13 风险表） | 缩略图只能在 worker 里预热，或退回 cgo |
| E3 SQLite 并发写 | `modernc.org/sqlite` 在 `_txlock=immediate` 下，两个进程并发写不丢更新、不报 busy（2 不变量 2、5.6） | 底座要换驱动或改成单进程写 |
| E4 Markdown 对拍 | goldmark + 自写变换能复现 `content/markdown.py` 的规则（5.12） | 渲染规则要改设计，或保留一个 Python 渲染边车 |
| E5 CodeMirror 6 在严格 CSP 下 | 后台编辑器换成 CodeMirror 6 后，`style-src 'self'` 下能正常显示和编辑（6.8） | 后台的 `style-src` 要放开一项 |

## 本轮范围

做：每个实验一个目录 `handoff/rounds/220-m0-experiments/eN-…/`，里面是能重跑的最小程序和脚本，结论写进 `report.md`（数字、没跑通的地方照实写）。

不做：

- 不改 `docs/design.md`、不新建 `server/`、`web/`（那是 221 之后）
- 不碰正式站和它的数据（E4 的语料用仓库里已有的 Markdown 用例和文档，不从正式站拉文章）
- 不新增依赖到现行站（实验的依赖只在各自目录里，`node_modules/` 和 Go 缓存不进仓库）

## 验收标准

每个实验有一个明确的「通过 / 不通过 / 有条件通过」结论和支撑它的数字；有条件通过的写清条件。能在测试机上跑的（E2 速度、E3 并发）在测试机上也跑一遍，因为本机是 Apple 芯片、正式站是 x86。
