# 077 实现报告

## 结论

**完成。** 个人中心 7 页、allauth 的 20 个页面、报名和战队的表单页都换成了设计体系；前台不再有 daisyUI 的类名，样式表去掉了 daisyUI 插件。**074–077 的前台重做到这里全部完成**，可以部署看效果了。

## 逐条结果

| 任务 | 结果 |
|---|---|
| 1 个人中心骨架 | 栏目头（`ACCOUNT · 昵称`、页面标题、页面级操作）；桌面左侧编号菜单 `01`–`07`，当前项左沿红线；手机上横向滚动的标签（当前项下沿红线）；资料不完整的提示条 |
| 2 个人中心各页 | 基本资料；游戏 ID（面板：等宽的游戏 ID、三个位置的段位带位置图标、更新时间、编辑 / 删除，HTMX 目标不变）；联系方式；我的战队、我的入队申请（表格，申请状态有形状）；我的报名、个人报名（表格）；我的内战；账号安全（一行一项：说明 + 按钮）；注销（红框提示 + 表单） |
| 3 allauth | `account/layout.html` 一栏窄表单；登录、注册右侧加「注册以后可以」三条说明（`account/_why.html`）；其余页面按钮、链接、提示换组件；改邮箱、邮箱列表手写 |
| 4 表单页 | 为战队报名（每个队员一行：序号、昵称、队长 / 交大标签、游戏 ID 下拉，有问题的一行红底）；个人报名（两步：游戏 ID、位置选择块）；报名详情（状态形状、名单快照表、状态历史）；创建战队；申请入队；战队管理（待审批申请的面板、成员表、资料、解散的红框） |
| 5 去掉 daisyUI | `input.css` 删插件和过渡主题：`app.css` 从 138KB 降到 64KB（gzip 24KB → 12.8KB）；`templates/core/home.html`（没有 Wagtail 首页时的兜底）也改了；设计 13.2.9、README、AGENTS.md 的过渡说明删掉 |
| 6 测试 | 见下 |
| 7 新组件 | `c-panel`（面板）、`c-link`（文字链接），写进设计 13.2.7，样张页加第 17 块；`components/registration_status.html` |

## 截图里发现并修掉的

- **个人中心在手机上整列溢出屏幕**：横向滚动的标签条放在网格里，网格项默认 `min-width: auto`，把整列撑到 617px，输入框和表格右半边被切掉。给菜单加 `min-w-0`。写了一个浏览器探针（找出超出视口、又不在横向滚动容器里的元素），在 360px 下把前台 33 个页面过了一遍，全部通过；把修复撤掉再跑，探针报 `NAV.font-nav 617`，确认它测得出来
- **导航在个人中心页标错栏目**：`/me/teams/` 高亮了「战队」、`/me/registrations/` 高亮了「赛事」——导航是按子串判断的。改成按路径开头判断
- **注册页的密码说明**：Django 的密码提示是 `<ul>`，放在 `<p>` 里不合法，浏览器把列表挪出去，样式全丢。帮助文字改用 `<div>`
- **单选框是方的**，和复选框分不清，「是否来自交大」看起来像能两个都选。改成圆的，设计 13.2.5 写明这是除状态点外唯一的圆形

## 设计偏差

改设计的地方（先改文档）：13.2.5 单选框是圆的；13.2.7 新增 `c-panel`、`c-link`；13.2.9 前台不能有 daisyUI 类名、有测试扫描；13.5 菜单编号改成 `01`–`07`（068 加了「我的内战」，设计还写着 6 项）。

## 验收输出

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
244 files already formatted

$ uv run python manage.py tailwind build --force
Built production stylesheet '/home/user/sjtu-ow/static/css/app.css'.

$ uv run pytest -q
945 passed in 245.67s (0:04:05)

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python manage.py render_error_pages   # git status deploy/：无变化
Wrote /home/user/sjtu-ow/deploy/error_pages/maintenance.html
```

936 → 945。`app.css` 64296 字节，gzip 后 12766 字节。Docker 构建未验证。

## 变异

`handoff/rounds/077-account-and-forms/mutate.py`（样式表那条变异改完会重新编译 `app.css`，还原后再编译一次）：

```
KILLED   模板里又写 daisyUI 的按钮  | 1 failed, 24 passed in 4.62s
KILLED   模板里又写 daisyUI 的底色  | 1 failed, 24 passed in 4.75s
KILLED   样式表又加载 daisyUI  | 1 failed, 25 passed in 4.55s
KILLED   导航按子串判断当前栏目  | 1 failed, 10 passed in 3.78s
KILLED   个人中心菜单不编号  | 1 failed, 11 passed in 4.33s
KILLED   个人中心菜单不标当前项  | 1 failed, 11 passed in 4.12s
KILLED   段位小段不用数字字体  | 1 failed, 12 passed in 4.52s
KILLED   待审核也画成对勾  | 1 failed, 27 passed in 4.54s
KILLED   撤回画成驳回  | 1 failed, 29 passed in 4.61s
9/9 killed
```

手机溢出没有写成单元测试（是排版问题，服务端测不出来），用上面的浏览器探针验证，撤掉修复时探针会报。

## 未完成 / 顺带发现

- **入队申请的坦克位写成「重装」**：`TeamApplication.role_tank` 的中文名和 `role_labels()` 用的是「重装」，设计和别处都叫「坦克」。战队管理页现在用位置组件，显示成「坦克」；申请表单上的勾选框还是「重装」。改字段的中文名要一个迁移，留给 078
- 手机上个人中心的标签条会横向滚动，当前页如果在后面几项（比如「账号安全」），打开时看不到当前项。可以用一行脚本滚到当前项，没做
- 本会话推分支，CI 没跑；测试机没部署

## 改动文件

```
assets/css/input.css                              去掉 daisyUI；c-panel、c-link、c-auth、圆形单选、帮助列表
templates/me/{base,_nav,_incomplete,profile,game_accounts,contacts,teams,registrations,security,delete}.html
scrims/templates/scrims/me.html
templates/account/*.html（20 个）、templates/account/_why.html（新建）、templates/account/snippets/*.html
tournaments/templates/tournaments/{register,individual_signup,registration_detail}.html
teams/templates/teams/{create,apply,manage}.html
templates/core/home.html
templates/components/{main_nav,form_field}.html
core/templates/core/styleguide.html
core/tests/test_design_system.py
docs/design.md（13.2.5、13.2.7、13.2.9、13.5）、README.md、AGENTS.md
handoff/STATUS.md、handoff/rounds/077-account-and-forms/
```
