# 188 首页「近期」固定成左大卡右列表；资讯、公告、战队固定条数（报告）

## 做了什么

1. `scrims/services.upcoming_scrims`：还没开始的已发布内战，按时间先后最多 5 条（`HOME_SCRIM_COUNT`），去掉 7 天窗口（`HOME_SCRIM_DAYS` 删了）。`schedule_home_refresh` 去掉「开始前 7 天刷新首页」那一次，截止和开始时的刷新照旧
2. `content/home.feature_tournament`：报名中的（截止最近）> 还没结束的（即将开始报名、报名已截止，比赛时间最近）> 结束的里面最近的一场；`Feature` 多了 `phase`。`home_tournaments()`：全部已发布的，加上最近结束的一场
3. `content/home.blanks()` 和上下文里的 `scrim_blanks`、`news_blanks`、`notice_blanks`、`team_blanks`：每块还差几个位置
4. `home_page.html`：
   - 近期永远 `c-upcoming--two`
   - 大卡按阶段写状态（报名中 / 即将开始报名 / 报名已截止 / 已结束）和说明；没有赛事时 `c-feature--empty`「还没有赛事」
   - 内战、资讯、公告、战队不够的位置用空行、空卡、空格补齐（里面是隐藏起来的真条目结构，高度一样），一条都没有时第一个空位写一句
   - 战队一支都没有时这一块照样在，区块头写「全部战队」
5. 样式：`c-feature--empty`、`c-row--empty`、`c-media--empty`、`c-teams__item--empty`；资讯 `c-media-grid--two`（640px 起固定两列）、战队 `c-teams--six`（1024px 起固定一行 6 格）
6. 设计 5.2、附录 C（顺带改正「首页资讯 6 篇」，5.2 和代码一直是 4 篇）、细节（v6.66）
7. 测试：按旧规则写的 7 条改成新规则，新加 5 条（赛事的三种情况、每块有一条时的空位、全空时第一个空位写一句）

用户发的「测试内战」在 12 天后（`days ahead 12.0`），旧规则只列 7 天内的，所以首页看不到；「测试赛事」现在也显示在大卡上了。

## 命令输出

测试机仍连不上，在本机跑。

变异（本机，17 处，全部被抓到）：

```
baseline green, 9 tests
caught columns follow the content again -> test_an_empty_agenda_keeps_both_places
caught no empty card -> test_an_empty_agenda_keeps_both_places
caught no empty card -> test_the_homepage_says_so_when_there_is_no_tournament
caught four scrims -> test_the_homepage_lists_the_next_five_however_far_off
caught four rows -> test_scrim_rows_keep_the_first_five_by_start
caught the 7-day window back -> test_the_homepage_lists_the_next_five_however_far_off
caught only open tournaments -> test_without_one_open_the_next_one_not_over_is_shown
caught the furthest one ahead -> test_without_one_open_the_next_one_not_over_is_shown
caught the first finished one -> test_when_all_are_over_the_last_one_is_shown
caught finished ones never offered -> test_when_all_are_over_the_last_one_is_shown
caught wrong badge before registration -> test_without_one_open_the_next_one_not_over_is_shown
caught scrim list shrinks -> test_every_block_keeps_its_places_when_there_is_little
caught scrim list shrinks -> test_an_empty_homepage_says_so_in_the_first_place_of_each
caught news grid shrinks -> test_every_block_keeps_its_places_when_there_is_little
caught news grid shrinks -> test_an_empty_homepage_says_so_in_the_first_place_of_each
caught notices shrink -> test_every_block_keeps_its_places_when_there_is_little
caught notices shrink -> test_an_empty_homepage_says_so_in_the_first_place_of_each
caught teams shrink -> test_every_block_keeps_its_places_when_there_is_little
caught every empty card says it -> test_an_empty_homepage_says_so_in_the_first_place_of_each
caught news columns follow the window -> test_every_block_keeps_its_places_when_there_is_little
caught news columns follow the window -> test_an_empty_homepage_says_so_in_the_first_place_of_each
caught homepage refreshed 7 days ahead again -> test_the_homepage_is_refreshed_when_the_scrim_closes_and_starts
restored and green; missed: none
```

第一次跑漏了「结束的里面挑最早的」：`home_tournaments` 只把最近结束的一场交给挑选函数，首页上看不出区别；补了一条直接调挑选函数的断言。

整组检查（本机）：

```
1 failed, 1719 passed, 1 skipped in 259.41s (0:04:19)
No changes detected
System check identified no issues (0 silenced).
```

红的是 `core/tests/test_calendar_feed.py::test_my_registrations_page_offers_it`（157 轮），单独连跑三次都通过：

```
1 passed in 0.94s
1 passed in 1.96s
1 passed in 0.74s
```

原因：订阅地址的令牌用 `signing.dumps`，里面带时间戳，每秒都不一样；页面生成和测试比对跨了一秒就对不上。和本轮无关，下一轮改成固定的地址（现在每次打开页面订阅地址都在变，旧的仍有效）。`docker build` 本机没跑，看 CI。

本机开发站（内置浏览器）：近期两栏 `677.25px 483.75px`，大卡和 4 条内战等高（400）。

正式站升级两次（第一次 `deploy_ship.sh 188` 时本机 SSH 被断开，服务器上的脚本照样跑完了；第二次 `188b` 用 `setsid` 脱离连接），之后在浏览器里量首页（1280 宽）：

```
upcoming: cols 677.25px 483.75px, card [677,477], list [484,477], rows [98,92,92,92,92]
news: cols 369.664px 369.664px, cards 4 × [370,342], first「还没有文章」
notices: rows [82,82,82,82,82], first「还没有公告。」
teams: cols 6 × 184px, tiles 6 × [184,273], first「还没有战队」
```

## 没做

- 内战空行比真条目矮 6px（92 对 98，真条目右边有状态标签），左右总高度仍然一致
- 内置浏览器面板在后台时截图画不全，这次只量了尺寸、没留截图
