# 066 实现报告

## 结论

**完成。** 组队大厅和只为它存在的东西全部删掉；新增「成员展示」`/members/`，管理员在后台「成员分组」里自定义分组、给组里加成员和职务。测试机已迁移上线，`/lfg/` 返回 404，`/members/` 由 worker 预渲染。

## 设计（v1.5.17）

第 6 章「组队大厅」整章换成「成员展示」（6.1 展示谁、6.2 分组、6.3 页面）；12.7 节换成 `MemberGroup`、`MemberGroupMembership` 两张表；12.4.2 游戏模式标为删除。其余几十处引用逐条改：概述、术语、应用划分、账号停用和注销、导出内容、角色表、功能权限、前台权限、首页快速入口、送审范围、路由、HTMX 示例、典型交互、预渲染分类、片段、刷新事件、后台菜单、限流、初始化、迁移约定、附录 B / C。改完设计里只剩三处有意保留的历史说明（第 6 章开头、12.4.2 标题、M3 里程碑的备注）。

### 我替用户定的细节（用户只说了「展示所有加入的用户」「分组标签后台可以自定义」）

| 问题 | 定的做法 | 理由 |
|---|---|---|
| 「加入的用户」是谁 | 账号未停用、至少验证过一个邮箱 | 没验证邮箱的注册不算完成；停用和注销的不该出现 |
| 显示什么 | 昵称、分组和职务、战队 | 隐私政策里这三样本来就是「所有访客可见」；**游戏 ID、段位、联系方式、邮箱、是否交大、注册时间都不显示** |
| 谁能管分组 | 超级管理员、内容编辑 | 和文章分类同一类「内容整理」的工作 |
| 一人多组 | 可以；也可以不在任何组 | 所有人都在最后的「全部成员」里 |
| 分组能不能暂时隐藏 | 有「显示」开关 | 组还没整理好时不用删 |

## 删除

| 删掉的 | 位置 |
|---|---|
| `lfg` 应用（车帖、发车 / 编辑 / 列表、片段、后台车帖管理、预渲染外壳、测试） | 整个目录 |
| 首页车帖数量片段 `home-lfg` | `templates/slots/home_lfg.html`、首页模板、`content/models.py` |
| 游戏模式 `GameMode`、后台菜单、`ensure_game_modes()`、`init_site` 里的初始数据 | `core/` |
| 全站设置 `lfg_max_active_posts`、`lfg_expire_hours` | `core/models.py` |
| 功能权限 `lfg_post`、送审类型 `lfg_note` | `accounts/models.py`、`moderation/` |
| 导航、页头「我要发车」、页脚、快速入口里的组队大厅 | 模板 |
| 只给车帖用的前端脚本（相对时间、复制按钮） | `static/js/app.js` |
| 组队大厅的样式 | `assets/css/input.css` |

**迁移**（测试机上已有示例车帖）：

- `core.0011_remove_lfg`：先 `DROP TABLE IF EXISTS lfg_lfgpost`（它有外键指向游戏模式表），删掉 `django_migrations` 里 `lfg` 的记录，再删 `GameMode` 和两个设置字段
- `accounts.0003_remove_lfg`：删掉 `lfg_post` 的功能权限规则
- `moderation.0002_remove_lfg`：删掉 `lfg_note` 的送审记录
- 旧的内容类型和权限用 Django 自带的 `remove_stale_contenttypes --include-stale-apps` 清，写进了 README 的升级说明。没放进迁移：迁移里删内容类型要处理 Wagtail 各表的级联，自带命令用完整的模型注册表做这件事更稳

## 新增：成员展示

| 部分 | 内容 |
|---|---|
| 应用 | `members/`：模型、服务、视图、模板、后台、信号、预渲染目标 |
| 页面 | `/members/`，照官网内页：左边米色侧栏列出分组（锚点）和「全部成员」；每个分组一个区块（名称、人数、简介、成员卡片：印章样式的首字、昵称、红色职务、战队链接）；最后「全部成员」按加入先后，带分组标签 |
| 后台 | 左侧菜单「成员分组」（Wagtail snippet）：名称、简介、显示、排序；同页维护组里的成员，下拉框显示「昵称（邮箱）」（昵称会重名），填职务、拖动排序。**只能加已加入的用户**，同组不能重复，分组名不区分大小写唯一 |
| 权限 | `init_site` 给内容编辑分配成员分组的增删改查 |
| 刷新 | 分组和成员增删改、邮箱地址保存或删除（邮箱验证就是一次保存）、账号停用或恢复、改昵称、战队任何变化（`refresh_team_list`）都请求重新生成 `/members/`；**登录只保存 `last_login`，不触发** |
| 注销和导出 | 注销时从所有分组移除；导出里的「车帖」换成「所在分组和职务」 |
| 导航 | 主导航加「成员」，页头常用入口「我要发车」换成「成员展示」，页脚、首页快速入口同样替换（快速入口补了「关于我们」） |

隐私政策草稿：删掉车帖相关的三处，「谁能看到你的信息」里写明验证邮箱后昵称、战队、分组和职务会出现在成员展示页。用户协议草稿删掉车帖的三处。

## 测试

`members/tests/test_members.py` 25 条：谁算已加入；全部成员按加入先后、不含游戏 ID 和邮箱；分组顺序、组内顺序、职务、简介、战队；已解散的战队不显示；隐藏分组不显示但人还在；分组跳过没加入的人；只能加已加入的用户；分组名大小写唯一；选成员时显示邮箱；内容编辑能进分组后台、赛事管理员不能；**后台表单端到端**：超级管理员新建带两个成员的分组、加没加入的人被拒、同一人加两次被拒（返回表单而不是 500）；分组增删成员、验证邮箱、改昵称、停用、战队变化都刷新页面，登录不刷新；页面在预渲染目标里；注销移出分组；导出含分组；组队大厅已不存在（应用、`/lfg/` 404、首页没有链接）。

改了的旧测试：LFG 的 N+1 检查换成成员展示页的 N+1 检查（查询数不随人数增长）；设计 15.3「联系方式不上公开页」的检查把 `/lfg/` 换成 `/members/`，并加上「成员页显示昵称、不显示游戏 ID」；附录 B 的枚举核对**补上了原来没核对的功能标识和送审类型**（车帖相关的值正是藏在这两个里）；附录 C 的设置核对、限流核对、文档路由核对去掉车帖。

## 变异

```
KILLED   停用的账号也算已加入  | 1 failed in 0.31s
KILLED   没验证邮箱也算已加入  | 1 failed in 0.31s
KILLED   不显示的分组也显示  | 1 failed, 4 passed in 0.59s
KILLED   分组顺序反了  | 1 failed, 2 passed in 0.53s
KILLED   组内顺序反了  | 1 failed, 2 passed in 0.53s
KILLED   全部成员按加入倒序  | 1 failed, 1 passed in 0.48s
SURVIVED  显示已解散的战队  | 144 passed in 10.53s
KILLED   分组里能加没加入的人  | 1 failed, 6 passed in 0.67s
KILLED   分组名可以重名  | 1 failed, 7 passed in 0.70s
KILLED   选成员时不显示邮箱  | 1 failed, 8 passed in 0.73s
KILLED   内容编辑没有分组权限  | 1 failed, 9 passed in 0.84s
KILLED   加成员不刷新  | 1 failed, 11 passed in 1.03s
KILLED   移除成员不刷新  | 1 failed, 11 passed in 1.00s
KILLED   验证邮箱不刷新  | 1 failed, 12 passed in 1.03s
KILLED   停用账号不刷新  | 1 failed, 12 passed in 1.04s
KILLED   改昵称不刷新成员页  | 1 failed, 12 passed in 1.03s
KILLED   战队变化不刷新成员页  | 1 failed, 14 passed in 1.11s
KILLED   注销不移出分组  | 1 failed, 16 passed in 1.14s
KILLED   导出不含分组  | 1 failed, 17 passed in 1.17s
KILLED   成员页不预渲染  | 1 failed, 15 passed in 1.11s
SURVIVED  不显示职务  | 144 passed in 10.42s
KILLED   不显示分组简介  | 1 failed, 2 passed in 0.53s
KILLED   不显示战队  | 1 failed, 2 passed in 0.53s
21/23 killed
```

两个幸存都是测试写弱了：

- **不显示职务**：断言「页面里有『社长』」，而那个人的昵称就叫「社长同学」。改成昵称「甲同学」，断言职务所在的标签
- **显示已解散的战队**：测试用 `disband_team()` 解散，它会同时删掉成员关系，所以页面自己的过滤从来没被用到。改成直接把战队标为已解散、保留成员关系

重跑：

```
KILLED   显示已解散的战队  | 1 failed, 3 passed in 0.59s
KILLED   不显示职务  | 1 failed, 2 passed in 0.54s
2/2 killed
```

23/23 被抓到，全部还原。

写测试时还踩到一个坑：modelcluster 的 `group.memberships.create()` **不会马上写库**，要等父对象保存。第一版测试这样建成员，三条测试「通过」是因为根本没有成员。已全部改成直接 `MemberGroupMembership.objects.create()`，N+1 那条同样改了。

## 本地演练

先在带示例车帖的本地样例库上跑一遍升级：

```
before: 2 lfg posts; 1 lfg migration rows
  Applying accounts.0003_remove_lfg... OK
  Applying core.0011_remove_lfg... OK
  Applying members.0001_initial... OK
  Applying moderation.0002_remove_lfg... OK
after: 0 lfg/gamemode tables; 0 lfg migration rows; 0 stale content types
```

浏览器里看过成员页（3 个分组、9 个人，2 个人不在任何组只出现在「全部成员」）和后台的分组编辑页（成员下拉框显示「昵称（邮箱）」、职务、上下移动、删除）。

## 测试机

```
--- 升级前:
车帖 2
--- 1. 升级前备份:
已备份到 /app/backups/sjtu-ow-20260919-131442.tar.gz（5.4 MB）
--- 2. 构建:
 Image sjtu-ow-test-web Built
 Image sjtu-ow-test-worker Built
--- 3. 迁移:
  Applying accounts.0003_remove_lfg... OK
  Applying core.0011_remove_lfg... OK
  Applying members.0001_initial... OK
  Applying moderation.0002_remove_lfg... OK
--- 4. 启动:
web: healthy
--- 5. 清理旧内容类型:
--- 6. init_site:
已分配成员分组权限：内容编辑 可管理成员分组
--- 7. 示例内容:
demo content ready
--- 8. 库里:
旧表 []
lfg 迁移记录 0
旧内容类型 0
[('社团干部', 3), ('赛事组', 3), ('内战组', 3)]
```

示例内容脚本（在临时目录，不进仓库）去掉了车帖，示例用户加上已验证的邮箱（这样才算「已加入」），另加 6 个示例成员和 3 个分组；示例账号仍然是不可用密码。

外部核对：

```
/lfg/ → 404   /lfg/new/ → 404
HTTP/2 200
cache-control: public, max-age=0, must-revalidate
groups: 3  members: 9  battletags: 0  emails: 0
home /lfg/ links: 0  home /members/ links: 5
Counter({'ready': 20}) [('/members/', 'ready')]
worker failures: 0
{"status": "ok", ... "disk": {"ok": true, "detail": "free space 76.6%"}
```

`cache-control` 是 Caddy 给静态页的头；原来 `/lfg/` 的预渲染记录在全量生成时被清掉了。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
237 files already formatted

$ uv run python manage.py tailwind build --force
Built production stylesheet '.../static/css/app.css'.

$ uv run python -m pytest -q
858 passed in 54.49s

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

868 → 858：删掉 `lfg` 的测试，加上成员展示的。

## 顺带发现（不在本轮做）

- **设计 4.1 说内容编辑能管理文章分类，但 `init_site` 从没给过这个权限**（原来的游戏模式也一样）。只有超级管理员能改分类。本轮只给了成员分组的权限，分类的留给下一轮
- 成员展示页没有分页。几百人以内一页没问题；社团规模大了再考虑
- 超级管理员用 `createsuperuser` 建的账号没有邮箱验证记录，不会出现在成员页。要出现，在后台给他加一条已验证的邮箱

## 改动文件

```
docs/design.md                                     v1.5.17
lfg/                                               删除
members/                                           新建（含迁移、模板、测试）
core/models.py、core/services.py、core/wagtail_hooks.py、core/apps.py
core/management/commands/init_site.py
core/migrations/0011_remove_lfg.py
accounts/models.py、accounts/services.py、accounts/migrations/0003_remove_lfg.py
moderation/models.py、moderation/services.py、moderation/migrations/0002_remove_lfg.py
moderation/templates/moderation/detail.html
content/models.py、content/templates/content/home_page.html
teams/services.py
templates/base.html、templates/components/{main_nav,icon}.html、templates/slots/home_lfg.html（删除）
core/templates/core/fonts/typography.html
assets/css/input.css、static/js/app.js
sjtu_ow/settings/base.py、sjtu_ow/urls.py、pyproject.toml
content/legal/privacy.md、content/legal/terms.md
测试：core/tests/{test_chapter15_audit,test_documented_urls,test_regeneration_events}.py、
      accounts/tests/{test_profile,test_account_deletion}.py、content/tests/test_content.py
README.md、AGENTS.md、handoff/STATUS.md
handoff/rounds/066-members-replace-lfg/
```
