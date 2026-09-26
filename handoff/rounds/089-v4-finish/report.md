# 089 M10 收尾 报告

## 做了什么

1. **去掉 v3 名字**
   - 样式表里的 `var(--tone-*)`、v3 令牌名、`--glass-*` 用脚本机械替换成 v4 名字，`@theme` 里的别名块、色调变量块、`bg-panel` 这类工具类别名删掉
   - 替换映射：
     - 色调变量：`tone-panel` → `surface`，`tone-sunken` → `surface-2`，`tone-accent` → `primary-text`，`tone-focus` → `primary`
     - 主色：`primary-deep` → `primary-text`，`primary-container` → `primary-soft`，`tertiary-container` → `warn-soft`
     - 表面：`surface-lowest` → `surface`，`surface-low` → `bg`，`surface-mid` / `surface-high` → `surface-2`，`surface-highest` → `line`
     - 文字：`on-surface*` → `fg*`
     - 描边：`outline-variant` → `line`，`outline` → `control`
     - 操作提示：`inverse-*` → `toast` / `on-toast`
     - 状态：`*-container` → `*-soft`
   - 13 个模板里的 `text-fg-red`、`border-rule`、`bg-surface-high` 换成 `text-primary-text`、`border-line`、`bg-surface-2`
2. **圆角**：`--radius-md/lg/xl`（v4 里都是 8px）删掉，样式和模板统一用 `radius-sm`
3. **字号**：样式表里剩下的 11 处小于 0.875rem 的字号调到 0.875rem，样张页两处 `text-xs` / `text-[0.6875rem]` 改 `text-sm`
4. **评论区**：标题从「评论 <徽标>」改成「N 条评论」（没有评论时「评论」）；`c-count` 样式删掉
5. **表单**：个人报名、战队报名、样张页里的分步去掉 `01`、`02` 编号；设计 13.2.6 补 `c-step`
6. **错误页**：`error.css` 加深色值（和站点一致），`theme-color` 分深浅；去掉 FORBIDDEN / NOT FOUND / MAINTENANCE 等英文标签和它的样式；页脚小字调到 14px；重新生成维护页
7. **删旧样式**：扫了一遍样式表里的 `c-*` 类名，模板和代码里都找不到的删掉 8 组：大号头像两种、评论数、占位图标、区块头的编号 / 英文 / 横线、侧栏编号和标题
8. **测试**（`core/tests/test_design_system.py`）
   - 样式表和前台模板里没有 v3 名字（替换了原来的「v3 名字是别名」）
   - 没有小于 14px 的字
   - 错误页没有英文标签、没有小字
   - 错误页的深色值和站点一致
   - 登录卡片的描边和圆角改用 v4 名字
   - 评论数的测试改成「N 条评论」
9. **文档**：设计 13.15；REVIEW-GUIDE 的 v4.0 一节；AGENTS.md 记 `default` 过滤器的坑；STATUS 里 M10 完成、测试机升级步骤改到 089（迁移一共 14 个，086 加了 `core/0013`）

## 验证

变异（`handoff/rounds/089-v4-finish/mutate.py`）：

```
BASELINE 59 passed in 9.66s
KILLED   样式表里又出现 v3 名字  | 1 failed, 32 passed in 10.65s
KILLED   模板里又用 v3 工具类  | 1 failed, 32 passed in 11.98s
KILLED   样式表里又有小于 14px 的字  | 1 failed, 34 passed in 11.57s
KILLED   模板里又用 text-xs  | 1 failed, 34 passed in 11.83s
KILLED   错误页深色少一个颜色  | 1 failed, 26 passed in 11.86s
KILLED   错误页又带英文标签  | 1 failed, 9 passed in 6.90s
KILLED   评论数又是徽标  | 1 failed, 18 passed in 11.67s
KILLED   又用回玻璃变量  | 1 failed, 32 passed in 12.19s
8/8 killed
```

整组检查（Windows 本机，`PYTHONUTF8=1`）：

```
All checks passed!
247 files already formatted
Built production stylesheet '...\static\css\app.css'.
1002 passed in 192.62s (0:03:12)
No changes detected
System check identified no issues (0 silenced).
```

视觉（无头 Edge 截整页；登录后的页面用测试客户端渲染成静态副本再截）：

- 深色：登录页、游戏 ID 与段位
- 浅色：登录后的文章页（评论框）
- 维护页：浅色、深色
- 375 宽：`/me/`、`/me/game-accounts/`、`/me/security/`、`/teams/new/`、文章页、`/accounts/signup/` 的 `scrollWidth` 都是 375

## 没做的

- 测试机升级（SSH 密钥在用户那边）
- 真手机上的深色模式未验证
