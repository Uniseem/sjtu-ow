# 163 剩下的页面补上 N+1 守卫（报告）

## 做了什么

1. `core/tests/test_chapter15_audit.py`：用已有的 `assert_no_n_plus_one`（3 份数据和 10 份数据的查询数要一样）加 8 条：资讯列表、首页、文章下面的评论（带回复）、站内搜索（文章加战队）、我的报名、我的内战、日历订阅、战队主页。数据里每个人都有头像图片（沿用这个文件的 `make_user`），按人取图也会显出来
2. **搜索的 N+1**（守卫查出来的）：`search/services.search_articles()`
   - 去掉多余的 `.specific()`：`ArticlePage.objects` 拿到的已经是文章本身，`.specific()` 让 Wagtail 再取一遍，`select_related("category")` 也跟着丢了，每篇命中的文章多一次查分类
   - 取地址时带上请求（`page.get_url(request)`，`search_all()` 和视图跟着传）：不带请求时 Wagtail 每篇都去缓存里读一次站点根路径，本站的缓存是数据库表，又是一次查询
   - 合起来每篇命中的文章多 2 次查询，一个分组最多 20 条，最多多 40 次

## 怎么发现的

162 之后临时写了一个探测（没提交），各页面放 3 份、10 份数据比查询数，全是平的。正式写守卫时搜索的数据多放了文章，红了：

```
E       AssertionError: /search/?q=审计：3 条数据用了 26 次查询，10 条用了 40 次——查询数随数据量增长，说明有 N+1。
```

分开放文章、战队、成员再量（临时脚本）：

```
PROBE articles: 26 -> 40
PROBE teams: 19 -> 19
PROBE members: 19 -> 19
```

去掉 `.specific()` 后 `22 -> 29`，再给 `get_url` 带上请求后 `21 -> 21`。

## 命令输出

各页的查询数（测试机，`-s` 打出来的）：

```
  /news/                               3 条 → 16 次查询 | 10 条 → 16 次查询
  /                                    3 条 → 20 次查询 | 10 条 → 20 次查询
  /news/audit-article-1/               3 条 → 31 次查询 | 10 条 → 31 次查询
  /search/?q=审计                        3 条 → 21 次查询 | 10 条 → 21 次查询
  /me/registrations/                   3 条 → 9 次查询 | 10 条 → 9 次查询
  /me/scrims/                          3 条 → 9 次查询 | 10 条 → 9 次查询
  /calendar/<签名>.ics                  3 条 → 17 次查询 | 10 条 → 17 次查询
  /teams/16/                           3 条 → 10 次查询 | 10 条 → 10 次查询
```

变异（测试机，9 处，全部被抓到）：

```
baseline green, 8 tests
caught news list without its joins -> test_no_n_plus_one_on_the_news_list
caught homepage without its joins -> test_no_n_plus_one_on_the_homepage
caught comments without their authors -> test_no_n_plus_one_under_an_article
caught search fetches articles twice -> test_no_n_plus_one_in_search_results
caught search looks up the site per article -> test_no_n_plus_one_in_search_results
caught my registrations without joins -> test_no_n_plus_one_in_my_registrations
caught my scrims without joins -> test_no_n_plus_one_in_my_scrims
caught calendar without its scrims -> test_no_n_plus_one_in_the_calendar_feed
caught team page fetches game IDs per person -> test_no_n_plus_one_on_a_team_page
restored and green; missed: none
```

第一版战队主页的变异是去掉成员的 `select_related("user")`，没抓到：下面的 `prefetch_related("user__game_accounts")` 本来就把人一起取回来了，那一处改了等于没改。换成去掉游戏 ID 的预取，抓到了；脚本里写了注释。

整组检查（测试机）：

```
1618 条测试分成 4 片
分片 1：405 passed in 37.14s
分片 2：405 passed in 38.04s
分片 3：404 passed in 38.23s
分片 4：404 passed in 36.25s
== 全部通过 (02:16:40)
```

演示站升级后，在服务器上用演示数据搜「内战」（9 篇文章命中），同一套代码分别不带、带请求取地址：

```
不带请求（旧的取地址方式） 查询 17 命中 {'articles': 9, 'events': 5, 'teams': 0, 'members': 0}
带请求（现在） 查询 9 命中 {'articles': 9, 'events': 5, 'teams': 0, 'members': 0}
```

响应时间在这台共用的机器上波动很大（三次 0.04、0.12、0.24 秒），没拿来比较。

## 没做

- 后台页面（活动数据、报名审核等）没加守卫：162 的探测里活动数据是平的（18 → 18）
