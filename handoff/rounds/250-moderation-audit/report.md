# 250 实现报告

## 结论

完成。审核域（AI 巡查之外的全部）和统一的操作记录做完；M5 留的 `ModerationSink` 接口接上了；测试机整组全绿，变异全部变红。

## 逐条结果

| 要求 | 结果 |
|---|---|
| 迁移 00014 | `moderation_items`（`UNIQUE(target_type, target_id, field, text_hash)`）、`audit_log`（统一一张：操作人、动作、对象类型、对象编号、数据 JSON、时间）、`site_settings.moderation_enabled` / `moderation_configured` |
| `platform/audit` | `Record(tx, actor, action, 对象, 数据)`（写在调用方的事务里）、`For(对象)` |
| 送审 R185–R188 | `Submit`：文本为空或开关没开/没配好都跳过；同一处没读过的旧文本被最新文本替换（自动保存的半成品不逐版排队，替换时失败计数清零）；文本相同（sha256）复用；读过的旧记录保留；昵称、宣言、队名、评论只存摘录，别的整篇存 `full_text`，摘录 2000 字 |
| 复核 R202 | 列表（默认待复核；「无风险」不进列表；待复核只显示 AI 已看过的；按状态/风险/类型/时间筛；带「AI 还没读」「没看成」计数和最近错误）、详情（作者的其他可疑内容数、不能发信的原因、操作历史）、处置（标无问题/已处置/忽略，写复核人、时间、说明，进操作记录）；只有 `moderation.review` 能力（内容编辑和超管） |
| 发信要求作者修改 R203 | 说明必填 ≤500 字；作者缺失/停用/没邮箱不能发；成功后算已处置，整段说明进操作记录；信里说明之前已经发过几次；直接发，不过待发信确认 |
| 清理 R204、R230 | `Cleanup`：状态不再是待复核、复核时间（没有就用创建时间）早于 180 天的删；没人处理过的永不删；接在 worker 的 04:00 夜任务上 |
| 接给各域 | `app.ModerationSink` 接口；账号（昵称、宣言，只在变了时送）、评论（发表和编辑后）、文章（发布时，标题+摘要+Markdown 原文）、内战说明（改了说明时）、战队、赛事；main 里统一 `SetModeration` |
| 导入 | `ImportLegacyModeration`：编号沿用、可重复跑、复核人/作者不存在的置空；接进 `sjtuow import`（决定 D5：割接前后台只读显示） |
| apigen | 重新生成（`/api/admin/moderation…`） |

## 验收输出

测试机：

- `go vet ./... && go test ./...`：日志 `20261009-111631-62ac37c`，全部 ok。
- 变异（`handoff/rounds/250-moderation-audit/mutate.py`，19 处）：首次 17 处红，漏两处：「读过的旧记录也被删」（测试里没覆盖「同一处既有读过的旧记录、又有没读过的，再送没读过的那份」）和「不查复核能力」（变异让变量没用到，编译失败）。测试补了这一步，变异脚本改成每处变异先 `go vet`、编译不过的单独报出来不算数（249 的教训）；两处重跑变红。
- 整组 `bash scripts/remote-check.sh`：全绿。

## 设计偏差

- 现行站的「是否已配置」看接口密钥或自建地址；新栈在全站设置还没做之前，用 `moderation_configured` 一个布尔列代表，M8 做全站设置页时由页面根据密钥/地址维护。
- 现行站的处置历史用 Wagtail 的操作日志；新栈用 `audit_log`，对象类型 `moderation_item`。
- 现行站复核页还有「试一下」「全量扫描」；这两样跟 AI 调用绑在一起，随巡查一起在割接后移植。

## 未完成 / 顺带发现 / 需要确认

- **AI 巡查**（规则 189–201、巡查提醒信）：决定 D5，割接后。
- 后台页面（M8）。待办里「AI 有内容没看成」（规则 205）的数据已有（`List` 的 `waiting`/`failed`/`last_error`），页面在 M8。
- 图片送审（`image` 类型）：现行站有这个类型但没有送审的调用点（头像撤下走另一条路），这里同样只留类型。

## 改动文件

`server/db/migrations/00014_moderation_audit.sql`；`server/internal/platform/audit/`；`server/internal/moderation/`（service、api、import 及测试）；`server/internal/app/moderation.go`；`server/internal/{accounts,comments,content,scrims}/`（`SetModeration` 及调用点，账号/评论/内战各一条测试）；`server/cmd/sjtuow/main.go`；`web/packages/api/src/gen/`；本目录。
