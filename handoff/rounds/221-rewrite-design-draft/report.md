# 221 实现报告

## 结论

完成，只有文档，没有代码改动。设计草案、12 号文档的修订、想法和遗留笔记、AGENTS.md 的重构一节都写了并推送。正式站没动。

## 逐条结果

| 任务 | 结果 |
|---|---|
| `docs/design-next.md` | 九节：怎么用（为什么不直接改 `design.md`、分工、生效方式）、为什么重写、决定表 D1–D9（D1–D4 用户拍板，D5–D7 按推荐，D8、D9 还没问）、架构（四个服务）、13 条不变量、章节对照（`design.md` 的每一章：保留 / 重写 / 替换 / 删除）、新栈独有的规则、对用户可见的变化（六条）、割接时合并的清单 |
| 12 号文档 | 5.6 `WriteTx` 加跨进程 `flock`；5.13 母版 2560 宽、方法 2、缩略图首次请求时生成、换 cgo 的判据；6.2 模板不写 charset/viewport、激活不一致在浏览器测试里算失败、Node 堆上限；6.8 CodeMirror 必须挂进 ShadowRoot；5.12 删除线两个波浪线、图注里不进行内代码；11.2 M0 一行；第 15 节修订记录；文件头的状态改成指向草案 |
| `13-ideas-and-followups.md` | A 等用户（crontab、升级正式站并跑 `scrub_originals`、R2、D8/D9、217 的六条）；B 现行站遗留（「冻结 ≠ 不修」，还没修的两组和处理建议，219 顺带发现的后台换队标不删旧图）；C 各里程碑开工前的验证和准备；D 新栈的想法；E 流程；F 想问用户的五个问题 |
| `AGENTS.md` | 加「重构进行中」一节和目录表一行 |
| `handoff/STATUS.md` | 更新 |

## 核对过的事实（写进文档之前）

- 测试机上没有 Go、没有 pnpm，Node 是 20.19.2：`ssh sjtu-ow-test 'which go pnpm; node -v'` 的输出是 `go: command not found`、`v20.19.2`。草案和笔记里写的是这个，不是我之前猜的「有 Node 24」
- 12 号文档里引用的 220 实验数字（flock 前后的 busy 次数、母版耗时、对拍 345/346、CodeMirror 两种挂法的违规）逐个对过 `handoff/rounds/220-m0-experiments/e*/RESULTS.txt`

## 没核对的

- `design-next.md` 第 5 节里每一章的去向是我按 12 号文档和调研文档判断的，没有逐章对着代码核对；M11 合并时要按第 8 节清单再过一遍
- 13 号文档 C 节里「`flock` 在两个容器共享卷上是否有效」「modernc 的在线备份在写事务外是否安全」是待验证的假设，写明了「没实测」

## 设计偏差

无。`docs/design.md` 本轮没动，仍是 v7.22。

## 需要确认 / 顺带发现

1. 用户回复里的「过几天再搞」我理解为：正式站的升级、crontab、`scrub_originals` 都等用户来；设计草案和笔记现在写完推送。如果「搞」指的是别的，请纠正
2. 13 号文档 F 节有五个问题（冻结的理解、pillow-heif、站长封面要不要保留原图、编辑器样子、不做只读上线），不急
3. 测试机上 Node 20 低于计划的 24；M1 开工前升级（装到检查目录，不动系统自带的）

## 改动文件

`docs/design-next.md`（新）、`docs/rewrite-research/12-architecture.md`、`docs/rewrite-research/13-ideas-and-followups.md`（新）、`docs/rewrite-research/README.md`、`AGENTS.md`、`handoff/STATUS.md`、本轮 `request.md`、`report.md`、`review.md`。
