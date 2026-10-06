# 213 复核结果（自查）

## 结论

自查通过。连做轮次，等独立复核后按 `REVIEW-GUIDE.md` 追加结论。

## 验证记录

- **变异验证 14 处全部被抓**（`mutate.py`，先跑基线确认绿再变异；恢复后清 `__pycache__`）：S1 两条、S7 一条、S2 两条、S3 两条、T2 两条、A8 两条、A9 一条、B3 两条。改回后基线全绿。原始输出在 report.md「验收输出」。2026-10-06 写报告前又完整重跑一遍取证，结果不变。
- **普查补测 7 处逐一变异确认会红**（`verify_census.sh`）：每处单独改坏、跑对应新测试、确认红、改回。其中 `accounts/forms.py:189` 变异后仍绿——没有糊弄过去，追下去确认是「唯一约束 + `violation_error_message` 同文案 + 视图 catch 回填」的等价兜底，并把测试的注释改成钉端到端行为（不声称钉表单那一层）。
- **34 个 survived 全部逐条读了代码和测试**才下结论，没有照清单猜。三处「等价」是实测出来的（models.py:255 手动复现撞车仍抛同文案；teams/forms.py:101 变异后旧测试照常绿，追到 service 层同文案再拦；teams/services.py:137/172 有现成的竞态测试钉着约束转换），其余等价判断给了具体机制（Wagtail Action 内部 `check()` 看过源码、`placed` 门口函数逐个对照过 `access.py`）。
- **逐行重读关键 diff**：
  - S2 的 `changed_roles`：`roles` 字典比较的是三个布尔位，`sign_up` 里清 placement 和 `_mark_teams_changed` 与换游戏 ID 同路径；`was_placed` 的 `is_selected or bool(team)` 覆盖缓冲区。
  - S3 的状态机：`publish` 只放行 DRAFT、`finish` 只放行 PUBLISHED；`tasks.py` 的 `finish_past_scrim` 自己先过滤 PUBLISHED，不会被新守卫误伤（读过调用点）。
  - A8 的 `reactivate_account`：`is_deleted` 只看邮箱后缀，`@deleted.invalid` 是注销时改的，正常用户碰不到；启用清 `deactivation_note` 有专门一条测试。
  - B3 的测试双向都验了：B 对 A 的图 403 且图没动，A 自己的 200。
- **整组检查在测试机**：1953 条分 4 片全绿，ruff / Tailwind / 迁移 / `check --deploy` / 错误页一致性 / Docker 构建全部通过。
- **212 的 CI 先确认过**：本轮开工前 `gh run list` 看 212 是绿的，没有带病开工。

## 发现的问题

- **必须修，本轮已修**：八条修复本身（request.md 列的 S1/S7/S2/S3/T2/A8/A9/B3）；普查 7 处真缺口的测试。
- **建议修（留给后面轮次）**：赛事的 `publish`/`finish` 有和 S3 同形的洞（只拦 CANCELLED），复核没列它、本轮不扩大范围，写进报告「顺带发现」；T7（赛事取消后还能审核）是设计空白，等用户拍板。

## 判断里最没把握的

- 「等价兜底」的 25 处没有逐一变异复核（只实测了其中 4 处）。其余的机制依据是读代码：Wagtail Action 的 `check()`、`placed` 门口函数与装饰器逐个对照、表单必填校验。如果哪一处读漏了调用路径，归类可能偏乐观——但每一处的机制都写进了报告，复核的人可以抽查。
- `pages.py:92` 归「等价/不可达」的依据是「内容编辑对首页子树有 change_page」这条授权（`content/services.py` 的 `_grant_page_perms`），如果以后首页子树之外出现 StandardPage，这个守卫会变成真守卫——它本来就该留着。

## 文档更新

- `docs/design.md`：v7.16（5.6、9.1、9.2、3.7、3.8、7.4 六处 + 附录 D 一行）
- `handoff/STATUS.md`：213 段落、头部 round/next/updated、轮次表加一行
- 轮次目录：request.md / report.md / review.md（本文件）/ mutate.py / verify_census.sh
