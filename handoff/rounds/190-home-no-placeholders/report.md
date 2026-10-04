# 190 首页去掉空位：位置和上限锁死，内容少就少（报告）

## 做了什么

1. `home_page.html`：去掉近期的空卡（`c-feature--empty`）和空行、资讯的空卡、公告的空行、战队的空格，以及「还没有赛事 / 最近没有内战 / 还没有文章 / 还没有公告 / 还没有战队」。内战、公告、战队的列表只在有内容时画；没有战队时这一块只留区块头「战队」「全部战队 →」
2. 188 锁死的位置和上限照留：近期 `c-upcoming--two` 两栏，内战最多 5 条，资讯 `c-media-grid--two`（宽屏固定两列）、公告 5 篇、战队 `c-teams--six`（宽屏固定一行 6 格）。新加：宽屏上大卡固定第一栏、内战列表固定第二栏，没有赛事时列表不会挪到左边
3. `content/home.py` 去掉 `blanks()` 和四个空位计数；`input.css` 去掉四种空位的样式
4. 设计 5.2、细节（v6.68）
5. 测试：188 写的空位测试改成「只显示有的、没有空位和那几句话」，加一条查内战列表固定第二栏的样式

## 命令输出

测试机仍连不上，在本机跑。

变异（本机，7 处，全部被抓到）：

```
baseline green, 4 tests
caught columns follow the content again -> test_an_empty_agenda_keeps_its_place_and_shows_nothing
caught columns follow the content again -> test_every_block_shows_only_what_there_is
caught the list drifts left -> test_the_scrims_keep_the_right_column_without_a_tournament
caught the card leaves its column -> test_the_scrims_keep_the_right_column_without_a_tournament
caught news columns follow the window -> test_every_block_shows_only_what_there_is
caught team tiles stretch -> test_every_block_shows_only_what_there_is
caught an empty team list drawn -> test_every_block_shows_only_what_there_is
caught an empty card again -> test_an_empty_agenda_keeps_its_place_and_shows_nothing
caught an empty card again -> test_the_homepage_leaves_the_card_out_when_there_is_no_tournament
restored and green; missed: none
```

整组检查（本机）：

```
1726 passed, 1 skipped in 241.20s (0:04:01)
No changes detected
System check identified no issues (0 silenced).
```

`docker build` 本机没跑，看 CI。

正式站升级（`deploy_ship.sh 190`，全量生成成功 11、失败 0，健康检查 ok）后，无头 Edge 1440 宽截整页：近期左边「测试赛事」大卡、右边一行「测试内战」（自己的高度，没有空行）；资讯、公告、战队只有区块头，下面是页面底色。

## 没做

- 没有内容的区块只留区块头，没写一句说明（用户说「没有发布就没有吧」）
