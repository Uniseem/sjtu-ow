# 101 头像能显示图片（报告）

## 做了什么

1. **设计 v6.1**：`design.md` 文档头、3.5.1 加「头像」一行（有字段、还没有设置入口）、3.8 注销清空头像、12.3 用户表加 `avatar`、12.13 缩略图缓存的例外（见第 5 条）、13.2.5 表、13.2.7 `c-avatar`、附录 D；`design-details.md` 版本和 2.3 重写
2. **字段**：`accounts/models.py` 的 `User.avatar`（外键 → `wagtailimages.Image`，`SET_NULL`），迁移 `accounts/0006_user_avatar`
3. **显示**：新模板 `templates/components/avatar.html`；14 处手写头像换成 `{% include "components/avatar.html" with person=… size=… %}`（作者行、作者卡、评论两处、入队申请、账号菜单、个人中心页头、成员小卡、个人主页、战队成员卡、退役列表、等待编队、首页和列表的文章卡）；成员名片上半部 `c-person__pic` 有图时放 400px 缩略图，`input.css` 加 `.c-person__pic img` 铺满
4. **刷新**：`accounts/signals.py` 的 `PUBLIC_FIELDS` 加 `avatar_id`，`update_fields` 写 `avatar` 或 `avatar_id` 都认；`refresh_nickname_pages` 加上离开过的战队主页
5. **注销**：`delete_account` 清空 `avatar`
6. **查询数**：`accounts/services.py` 新函数 `with_avatars(queryset, path)`（`select_related` 头像 + `prefetch_related` 缩略图），用在成员展示、战队主页的现役和退役、入队申请、等待编队、评论、首页最新文章、置顶文章、文章列表、同栏目文章
7. **缩略图缓存**（`settings/base.py`）：Wagtail 每取一次缩略图都往缓存里记一笔，原来记在数据库缓存里，一张图就是几次写库。加了 `renditions` 别名，用进程内存（10 分钟、最多 2000 条）。`conftest.py` 每个测试前清空它（测试回滚后图片编号会重复）
8. **顺带修**：文章卡片的链接 `{{ article.url }}` 每张卡读一次数据库缓存里的站点根路径（下面的输出），换成 `{% pageurl article %}`（`post_card.html`、首页近期的文章行）。这是原来就有的 N+1，本轮的文章列表审计会因为它红，改动两行，所以一起修了
9. **测试**：新文件 `accounts/tests/test_avatar.py`（15 条）；`core/tests/test_chapter15_audit.py` 的测试用户都带头像、媒体文件写到临时目录、计数前先访问一次（缩略图只在第一次显示时生成）并清空缩略图缓存

## 命令输出

N+1 审计在测试用户带上头像、还没改查询时：

```
E       AssertionError: /members/：3 条数据用了 75 次查询，10 条用了 206 次——查询数随数据量增长，说明有 N+1。
```

改完以后（第 15 章原有的六个审计）：

```
  /teams/                              3 条 → 4 次查询 | 10 条 → 4 次查询
.  /members/                            3 条 → 7 次查询 | 10 条 → 7 次查询
.  /tournaments/                        3 条 → 3 次查询 | 10 条 → 3 次查询
.  /scrims/                             3 条 → 3 次查询 | 10 条 → 3 次查询
.  /scrims/67/                          3 条 → 4 次查询 | 10 条 → 4 次查询
.  /tournaments/3/                      3 条 → 6 次查询 | 10 条 → 6 次查询
6 passed, 24 deselected in 3.87s
```

新加的文章列表审计第一次跑：

```
E       AssertionError: /news/：3 条数据用了 17 次查询，10 条用了 24 次——查询数随数据量增长，说明有 N+1。
```

用一个临时测试把 5 篇文章的列表页查询按语句计数，多出来的是站点根路径：

```
7 SELECT "cache_key", "value", "expires" FROM "django_cache" WHERE "cache_key" IN (':2:wagtail_site_root_paths')
```

换成 `{% pageurl %}` 后，新加的四个审计：

```
  /teams/405/                          3 条 → 11 次查询 | 10 条 → 11 次查询
  /tournaments/3/                      3 条 → 7 次查询 | 10 条 → 7 次查询
  /news/busy-article/                  3 条 → 29 次查询 | 10 条 → 29 次查询
  /news/                               3 条 → 14 次查询 | 10 条 → 14 次查询
16 passed in 11.33s
```

（临时测试 `accounts/tests/test_zz_debug.py` 用完删了，不在提交里。）

变异（`handoff/rounds/101-avatars/mutate.py`，17 处）第一次跑：

```
baseline green, 14 tests
caught the component ignores the picture -> test_a_face_is_the_picture_when_there_is_one
caught the component ignores the picture -> test_the_account_menu_shows_your_own_picture
caught plain still draws the scene -> test_without_a_picture_a_face_is_the_initial_on_its_scene
MISSED a spot draws the face by hand -> test_no_template_draws_a_face_by_hand
caught a spot draws the face by hand -> test_the_team_page_shows_members_and_former_members
caught the member card ignores the picture -> test_the_member_page_shows_the_picture_on_the_card_and_in_the_list
caught a new picture regenerates nothing -> test_a_new_picture_regenerates_the_pages_that_show_it
caught update_fields naming the field is missed -> test_a_new_picture_regenerates_the_pages_that_show_it
caught former members' team pages go stale -> test_a_former_members_team_page_is_regenerated_too
caught deletion keeps the picture -> test_deleting_the_account_drops_the_picture
caught thumbnails are not prefetched -> test_no_n_plus_one_on_a_team_page
caught the member list loads faces one by one -> test_no_n_plus_one_on_the_member_page
caught the team page loads members' faces one by one -> test_no_n_plus_one_on_a_team_page
caught the team page loads former members' faces one by one -> test_no_n_plus_one_on_a_team_page
caught the pool loads faces one by one -> test_no_n_plus_one_on_the_individual_pool
caught comments load faces one by one -> test_no_n_plus_one_on_an_article_with_comments
caught the article list loads faces one by one -> test_no_n_plus_one_on_the_article_list
caught cards look up the site root each -> test_no_n_plus_one_on_the_article_list
caught thumbnails are noted in the database cache -> test_no_n_plus_one_on_a_team_page
restored and green; missed: [('a spot draws the face by hand', 'accounts/tests/test_avatar.py::test_no_template_draws_a_face_by_hand')]
```

漏的那条：「模板里不手写头像」只要求那一行不含 `avatar`，而手写的头像本身带 `c-avatar` 类名，所以放过了。改成要求那一行判断 `avatar_id`（只有名片上半部这样写），只重跑这一处：

```
baseline green, 2 tests
caught a spot draws the face by hand -> test_no_template_draws_a_face_by_hand
caught a spot draws the face by hand -> test_the_team_page_shows_members_and_former_members
restored and green; missed: none
```

整组检查（开发服务器停着，先 `tailwind build --force`）：

```
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1229 passed in 164.58s (0:02:44)
```

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
268 files already formatted
$ uv run python manage.py makemigrations --check --dry-run
No changes detected
$ … manage.py check --deploy
System check identified no issues (0 silenced).
```

## 发现的问题（不在本轮修）

- **注销不清个人宣言**：`delete_account` 不清 `motto`，设计 3.8 也没写；注销的人写过的文章，作者卡上的宣言还在（署名已经是「已注销用户」）
- **作者的头像、昵称改了，首页和文章列表不刷新**：`refresh_nickname_pages` 只刷文章页本身，列表卡片上的作者行要等每天凌晨的全量生成。改昵称原来就是这样
- **测试往项目的 `media/` 里写图**：`content/tests` 的 `_image()` 等没有改 `MEDIA_ROOT`，本机 `media/original_images/` 里攒了几十张 `tournament-cover_*.png`（这次的演示备份里也带上了）

## 未验证

- 上传入口、后台设置入口都没有，所以「管理员在后台换头像」这条路径不存在、没测
