# 213 权限和状态守卫（S1、S7、S2、S3、T2、A8、A9、B3 + 普查 34 个 survived）

## 背景

210 全站复核（`handoff/rounds/210-full-review/review.md`）建议顺序的第 2 步：权限和状态守卫，每条补「拆掉就红」的测试。211 修了唯一的高（D1），212 修了自动保存那一批，本轮做这一批。条目编号即复核报告里的编号（中 2 条、低 6 条）：

- **S1**（中）：被禁言的人仍能编辑旧评论、编辑不限流。`comments/services.py` 的 `edit` 只查本人和可见，不查 `can_comment`（功能权限、文章是否关闭评论）；视图没有 `_too_many`
- **S7**（低）：作者能删除已被隐藏的评论（编辑拦了、删除没拦），正文清空后后台只剩空行（`comments/services.py:299-310`）
- **S2**（低）：分队后玩家改「能打的位置」，分队结果不更新也不提示。`sign_up` 只在换游戏 ID 时清 placement 并标 `roster_changed_at`，只改 roles 什么都不做；缓冲区的人换 ID 被清掉 `is_selected` 也不标记（`scrims/services.py:179-192`、设计 9.2）
- **S3**（低）：内战 `finish` 没有状态守卫、`publish` 只拦 CANCELLED：已取消的内战能被「标记已结束」重新上列表；空草稿 finish 后 `is_public` 为真公开可访问；finished 能 publish 回去。对比 `tournaments/services.finish` 要求 PUBLISHED（`scrims/services.py:311-334`、`scrims/admin_views.py:42-58`）
- **T2**（低）：队长能把队长转给已停用的账号，战队随即死锁；管理页对停用成员也显示「转让队长」。`assign_captain` 有这道检查（179 补的），`transfer_captain` 没有（`teams/services.py:459-482`、`teams/templates/teams/manage.html:76-84`）
- **A8**（低）：后台停用/启用直接改 `is_active`，不走 service（设计 17.3）；启用不清 `deactivation_note`；对注销过的账号也能点「启用」，`can_use()` 对它变 True（`backoffice/views/members.py:170-195`）
- **A9**（低）：`delete_account` 清了 `is_staff`、密码、邮箱、组，没清 `is_superuser`；配合 A8，曾是超管的账号能带着超管权限被「启用」回来（`accounts/services.py:368-411`）
- **B3**（低）：图片「改」「删」两道按张的守卫只有超管测过，拆掉不会红。门 `uses_images` 只要求某个集合上有 add/change/choose，投稿者在「投稿图片」只有 add+choose，「只能改删自己传的」靠的就是视图里两个 `if`（`backoffice/views/images.py:153-154,198-201`）

外加 210 守卫普查的收尾：34 个 survived（改坏后全量测试仍绿，`rounds/210-full-review/results.jsonl`）逐个判断——真没测到的补测试，等价变异或有另一层兜着的注明理由。

**T7 不在本轮**：赛事取消/结束后还能审核是设计空白，等用户拍板。

## 本轮范围

做：

1. S1：`comments/services.py` 的 `edit` 加和 `create` 一致的权限检查（禁言、文章关评论）；视图 `edit` 加限流（和 create 同一个限额）
2. S7：`comments/services.py` 的删除：已被隐藏的评论，作者不能删（后台管理员的隐藏/恢复走自己的路径，不受影响——读代码确认）
3. S2：`sign_up` 里 roles 变化按游戏 ID 变化同样处理（清 placement、标 `roster_changed_at`）；缓冲区的人被清掉 `is_selected` 时也标记
4. S3：`scrims/services.py` 的 `finish` 要求 PUBLISHED（对照 tournaments）；`publish` 只许 DRAFT；发布时查必填（对照 206 赛事的 `missing`）；管理页按钮按状态显示
5. T2：`transfer_captain` 拒停用账号（`TeamError`）；管理页停用成员那行不显示「转让队长」
6. A8：后台停用/启用走 `accounts/services.py` 的 service 函数；启用清 `deactivation_note`；注销过的账号不能启用（按钮也不给）
7. A9：`delete_account` 清 `is_superuser`
8. B3：补测试——投稿者 A 传图，投稿者 B POST `image_edit`/`image_delete` 应 403 且图还在
9. 每条新规则配「拆掉就红」的测试，做变异验证
10. 34 个 survived 逐个判断，结论写进 report.md（真没测到且值得补的补测试，等价/有兜底的注明）
11. 设计文档同步：9.2（roles 变化）、内战状态规则、3.x/4.x（停用启用、注销清超管）、评论的编辑/删除权限；附录 D 记版本

明确不做：

- T7（等用户拍板）；A2、A12、B11 同样
- 复核报告的其余条目（214 worker 和日志 C1–C3，215 Caddy 和预渲染 C4/C5/C6/C9/F1，其余低的顺手轮）
- 不改变这些守卫之外的可见行为；不加新依赖

## 任务

1. 读 `comments/services.py`、`comments/views.py`：create 的权限和限流长什么样，edit/delete 照齐
2. 读 `scrims/services.py` 的 `sign_up`、`finish`、`publish` 和 `tournaments/services.py` 的对照实现
3. 读 `teams/services.py` 的 `assign_captain`/`transfer_captain`、`accounts/services.py` 的停用/启用/注销相关函数、`backoffice/views/members.py` 的停用启用视图
4. 读 `backoffice/views/images.py` 的两道守卫和 `image_policy`
5. 实现 + 测试；每处守卫做变异验证（改坏 → 红 → 改回）
6. 34 个 survived：按 results.jsonl 逐条过代码，分类「补测试 / 等价变异 / 有另一层」，补了的进变异清单
7. `docs/design.md` 先改再改代码的条目照硬规则 1 办，附录 D 记 v7.16

## 验收标准

- `bash scripts/remote-check.sh` 全绿
- 每条新规则的变异验证记录在 report.md
- 34 个 survived 每条都有结论（补测试 / 等价 / 有兜底）
- CI 推送后看结果；正式站备份后升级
