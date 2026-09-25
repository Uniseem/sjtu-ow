# 078 复核结果（自查）

## 结论

**通过（自查）**，待独立复核。

## 验证记录

1. 整组检查全绿（948 passed）；变异 7/7
2. **保留片段的测试不是抄一遍清单**：它从 Django 的路由表里取第一段路径，再并上 Caddy 自己提供的 `static`、`media`，和 `RESERVED_CHILD_SLUGS` 比。写的时候把路由表打出来看，发现 `request.md` 里没想到的 `registrations` 和 `_util` 也漏了；变异里分别去掉 `search`、`registrations`、`static`，都红
3. **迁移不动表**：`sqlmigrate teams 0002` 是 `(no-op)`，升级时不会重建 `teams_teamapplication`
4. **标签条**：真浏览器里验证了滚动，并且撤掉那一行后当前项确实看不到，不是碰巧可见
5. **上线步骤的每条命令都对照过仓库**：命令名（`backup`、`prerender`、`remove_stale_contenttypes`、`init_site`）都存在；Webhook 那一行的原文从 067 之前的 `deploy/crontab.example` 里查到，确认升级后它会报 ImportError；`main` 当前在 073，分支是它的直接后代，可以 `--ff-only`；`main` 上 073 的 CI 是绿的（GitHub Actions 第 28 次运行）

## 发现的问题

- ink-3 的对比度不到 AA（见报告），转 079
- 写 REVIEW-GUIDE 时一开始写了「没有内战的两周应显示空态」，对照模板发现日程带其实照样画 14 天、下面加一句说明，改成了实际行为；对比度那条一开始写成「已截止」的状态也在用 ink-3，查样式表发现状态文字是 `fg-2`，只有图形用 ink-3，也改了。**写指南时容易凭印象描述自己做过的东西**，每条都要回到代码核对

## 判断里最没把握的

1. 升级步骤没在真机上走过。命令都是照 053 实际走通的部署步骤和设计 16.8 拼的，但 066 → 078 中间隔了 12 轮、4 个应用的迁移，第一次升级最好先看 `migrate --plan`
2. `_util` 保留与否影响很小（只有 Wagtail 的两个内部地址），保留是为了让测试的规则简单：所有 Django 固定接管的第一段都保留

## 文档更新

- `docs/design.md`：v2.0.1（13.13.3、5.4.3、附录 D）
- `handoff/REVIEW-GUIDE.md`：074–078 一节
- `handoff/STATUS.md`：上线计划、第 19、20 条、里程碑、轮次表
