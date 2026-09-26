# 085 个人中心、登录注册、表单页（M9 收尾）报告

## 做了什么

1. **个人中心**
   - `accounts/views.py` 的 `ME_NAV` 从三元组改成四元组，最后一项是图标名（user、id、phone、shield、trophy、calendar、lock）
   - `templates/me/_nav.html` 每项先画图标（`size-5 c-sidenav__icon`），去掉 `01`–`07` 编号
   - `templates/me/base.html` 页头去掉「ACCOUNT · 昵称」眉标，一级标题下一行是首字头像（`c-avatar--sm`）和昵称
2. **登录注册**
   - `templates/account/layout.html` 去掉眉标，表单放进 `c-auth`：最宽 28rem、1px `tone-line` 描边、`radius-xl` 圆角
   - `templates/account/_why.html` 改成 `c-why` 色调卡片：三项各带一个色调图标片（日历、盾牌、笔），去掉粗线和编号
3. **表单页**：战队的申请、创建、管理，赛事的个人报名、战队报名、报名详情，六页去掉英文眉标
4. **评论区**：标题里的数量从借用 `c-comments__count` 改为 `c-count`
5. **样张页**、`templates/core/home.html`：跟着去掉编号和眉标的写法
6. **测试**
   - `core/tests/test_design_system.py` 新增和改写了这些测试：
     - 菜单每项一个图标、7 个图标互不相同、没有 `c-sidenav__index`、当前项唯一
     - 个人中心页头没有 ACCOUNT，有首字头像和昵称
     - 登录页是 `c-auth` 卡片，`input.css` 里的 `.c-auth` 块有描边和 `radius-xl`；`c-why` 有三个图标片、没有 `border-fg`
     - 八个表单模板里没有 `c-eyebrow`
     - 全部前台模板里没有 `border-fg`、`border-t-2`、`border-b-2`、`border-y-2`
   - `comments/tests/test_comment_extras.py`：评论区标题的数量是 `c-count`
7. **文档**
   - 设计 v3.0.1：13.5 页头和菜单图标；13.2.7 补 `c-sidenav`、`c-auth`、`c-why`，栏目头不写英文眉标；附录 D 加一行
   - `handoff/REVIEW-GUIDE.md`：v3.0 一节补 082–085
   - `handoff/STATUS.md`：M9 完成；测试机升级步骤从「066 → 079」改成「066 → 085」，迁移清单补上 082 的两个

## 验证

变异（`handoff/rounds/085-account-forms/mutate.py`）：

```
BASELINE 57 passed in 9.78s
KILLED   菜单用回编号  | 1 failed, 12 passed in 7.89s
KILLED   菜单两项共用一个图标  | 1 failed, 12 passed in 9.41s
KILLED   个人中心页头又带眉标  | 1 failed, 13 passed in 9.67s
KILLED   个人中心页头没有头像  | 1 failed, 13 passed in 9.71s
KILLED   登录不在卡片里  | 1 failed, 14 passed in 8.32s
KILLED   卡片样式没了圆角  | 1 failed, 14 passed in 6.94s
KILLED   注册以后可以用回粗线  | 1 failed, 14 passed in 7.03s
KILLED   注册以后可以少一个图标  | 1 failed, 14 passed in 6.14s
KILLED   报名页又带英文眉标  | 1 failed, 50 passed in 7.05s
KILLED   建队页又带英文眉标  | 1 failed, 47 passed in 11.69s
KILLED   前台别处画粗线  | 1 failed, 52 passed in 11.76s
KILLED   评论数借用旧样式  | 1 failed, 17 passed in 11.19s
12/12 killed
```

整组检查（Windows 本机，`PYTHONUTF8=1`）：

```
All checks passed!
247 files already formatted
Built production stylesheet '...\static\css\app.css'.
FAILED tournaments/tests/test_adhoc_teams.py::test_the_board_carries_what_the_script_and_the_view_need
1 failed, 997 passed in 278.13s (0:04:38)
No changes detected
System check identified no issues (0 silenced).
```

失败的那条单独重跑：

```
1 passed in 1.16s
```

这条测试断言整页 HTML 转小写后不含 `cdn`（确认没有外部脚本），而编队页（`admin/teams.html`）的表单里有随机生成的 CSRF 令牌。**推测**是令牌偶尔恰好含有这三个字母，没有抓到失败那次的页面来证实。这条断言是 070 轮加的（`git log -S` 查到 627a17c），本轮没碰这个页面和这条测试。**没有在本轮修**（不扩大范围），留给下一轮：改成只查 `<script src=` 和 `<link href=` 的地址。

视觉：

- 1280 宽：登录页左边卡片、右边「注册以后可以」色调卡片；个人中心侧栏带图标，当前项 `primary-container` 底，页头下是头像和昵称
- 375 宽：`/accounts/login/`、`/accounts/signup/`、`/me/`（登录后渲染成静态副本看）`scrollWidth` 都是 375，没有横向溢出；个人中心的菜单在手机上是横向标签条

## 顺带发现的

1. 上面那条 `cdn` 偶发失败的测试
2. 手机上个人中心的标签条不带图标，和桌面侧栏不一致（review.md 记为主观取舍）
