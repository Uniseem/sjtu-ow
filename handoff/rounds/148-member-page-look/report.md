# 148 个人主页定版式（报告）

## 做了什么

1. `members/templates/members/detail.html`：
   - 页头 `c-stage c-stage--team`：底图、大头像（`fill-288x288`，和战队的大队标一样）、分组和职务、昵称、宣言（`c-stage__lede`）
   - 事实栏 `data-member-facts`：常用位置、段位、现役战队、文章
   - 本人才有 `data-owner-panel`：编辑资料、缺项提示
   - 所在战队：`c-rows` 紧凑行，队标懒加载
2. `assets/css/input.css`：`.c-stage__facts dd.is-stale`（过期段位变灰）
3. `members/views.py`：注释
4. 设计 v6.41（6.4，含继续 `noindex` 的决定）
5. 测试：
   - `members/tests/test_member_page.py` 两条按新写法改断言、加 1 条
   - `accounts/tests/test_avatar.py` 个人主页头像尺寸从 176 改成 288
   - `scripts/screens.py` 加个人主页的截图

## 两处被现有测试拦下的

- `core/tests/test_images.py::test_pictures_below_the_first_screen_load_lazily`：新的战队行里队标没写 `loading="lazy"`，补上
- `accounts/tests/test_avatar.py`：个人主页上的头像尺寸变了，测试本意是「个人主页显示头像」，改成横幅用的尺寸

## 命令输出

变异（测试机，7 处，第一次全部被抓到）：

```
baseline green, 3 tests
caught no team count -> test_the_banner_counts_teams_and_articles
caught no article count -> test_the_banner_counts_teams_and_articles
caught no positions -> test_the_page_shows_what_is_public_and_nothing_else
caught no rank -> test_the_page_shows_what_is_public_and_nothing_else
caught big team cards again -> test_the_banner_counts_teams_and_articles
caught the owner panel for everyone -> test_only_the_owner_sees_edit_and_hints
caught no owner panel -> test_only_the_owner_sees_edit_and_hints
restored and green; missed: none
```

整组检查（测试机）：

```
1575 条测试分成 4 片
分片 1：394 passed in 39.66s
分片 2：394 passed in 39.35s
分片 3：394 passed in 39.80s
分片 4：393 passed in 37.96s
== 迁移 (22:54:04)
No changes detected
== 生产配置 (22:54:06)
System check identified no issues (0 silenced).
== 错误页和模板一致 (22:54:07)
== Docker 镜像 (22:54:08)
构建成功：0084735c13ce
== 全部通过 (22:54:08)
```

截图（测试机，375 宽）：别人看和本人看各一张，横幅、事实栏、紧凑的战队行、本人的编辑块都正常。演示站升级后 `/members/5/` 返回 200。

## 没做 / 未验证

- 桌面宽度没截
