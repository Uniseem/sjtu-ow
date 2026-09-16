# 协作流程

这个目录是 **Grok（实现方）** 和 **Claude（设计与复核方）** 之间的交接区。用户只需要在两边分别说「继续」，双方各自读 `handoff/STATUS.md` 决定自己该做什么。

## 三个角色

| 角色 | 负责 | 不做 |
|---|---|---|
| Claude | 维护 `docs/design.md`；写每轮的要求（`request.md`）；复核实现（`review.md`） | 不写业务代码（除非用户明确要求） |
| Grok | 按 `request.md` 实现；写实现报告（`report.md`） | 不改 `docs/design.md`，不扩大本轮范围 |
| 用户 | 在两边转述「继续」；对待定问题拍板 | — |

## 目录结构

```
docs/design.md                     唯一的设计依据
handoff/README.md                  本文件：流程规则
handoff/STATUS.md                  当前状态，规定下一步由谁动手
handoff/rounds/<序号>-<名字>/
    request.md                     本轮要求（Claude 写）
    report.md                      本轮实现报告（Grok 写）
    review.md                      本轮复核结果（Claude 写）
    artifacts/                     可选：命令输出、截图等证据
```

轮次目录按 `001`、`002`、`003` 递增，名字用英文短横线小写，比如 `003-m0-hardening`。

## 一轮的流程

1. **Claude** 新建轮次目录，写 `request.md`，把 `STATUS.md` 的 `next` 改成 `grok`
2. 用户对 Grok 说「继续」
3. **Grok** 读 `STATUS.md` → 找到当前轮次 → 读 `request.md` 和 `docs/design.md` 里被引用的章节 → 实现 → 写 `report.md` → 把 `next` 改成 `claude` → 提交 git
4. 用户对 Claude 说「继续」
5. **Claude** 读 `report.md` → 独立验证（自己跑命令，不采信报告里的结论）→ 写 `review.md` → 需要改设计文档就改 → 新建下一轮 `request.md` → 把 `next` 改成 `grok`
6. 回到第 2 步

## 硬规则

1. **`docs/design.md` 是唯一设计依据。** Grok 发现设计有问题，写在 `report.md` 的「设计偏差」一节里，由 Claude 更新文档，不要自己改
2. **谁写完谁更新 `STATUS.md`** 的 `next` 和 `updated` 字段
3. **Grok 每轮结束提交一次 git**，提交信息以轮次号开头，比如 `003: fix health check busy handling`
4. **报告里的验收输出必须是真实执行过的命令输出**。没跑的写「未验证」，不要写推测结果。Claude 会自己重跑一遍
5. **不新增依赖。** 确实需要，在 `report.md` 里说明理由并停下来等确认
6. **不要在本轮范围之外改动**。顺手发现的问题写进 `report.md` 的「顺带发现」，由下一轮处理
7. 不确定的地方**问，不要猜**。写在 `report.md` 的「需要确认」里

## 文件格式

### request.md

```
# <轮次号> <标题>
## 背景        为什么做这一轮
## 本轮范围    做什么 / 明确不做什么
## 任务        逐条，每条带验证方式和期望结果
## 验收标准    要跑哪些命令、期望输出
## 输出要求    写进 report.md 的哪些小节
```

### report.md

```
# <轮次号> 实现报告
## 结论        一句话
## 逐条结果    对应 request 的每条任务
## 验收输出    真实命令输出
## 设计偏差    和 docs/design.md 不一致的地方，交给 Claude 改文档
## 未完成 / 不同意
## 顺带发现    本轮范围外的问题
## 需要确认
```

### review.md

```
# <轮次号> 复核结果
## 结论        通过 / 需返工
## 验证记录    Claude 实际跑了什么，结果如何
## 必须修
## 建议修
## 认可的判断
## 文档更新    Claude 改了 design.md 的哪些地方
```
