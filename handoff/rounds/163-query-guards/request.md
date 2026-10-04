# 163 剩下的页面补上 N+1 守卫

## 背景

继续自主推进。站长关心的「人多了会不会慢」：设计 15.1 要求查询数不随数据量增长，`core/tests/test_chapter15_audit.py` 已经守着战队列表、成员页、赛事列表和详情、内战列表和详情。最近几十轮加了不少页面和内容（首页的我的安排、日历订阅、评论、个人中心几页），没有守卫。

162 之后在测试机上临时写了一个探测：每页先放 3 份数据量一次查询数，再加到 10 份量一次。下面这些页都是平的（没有 N+1），但以后谁去掉一个 `select_related` 都不会有测试发现：

```
PROBE /news/                                   3->16  10->16  flat
PROBE /                                        3->20  10->20  flat
PROBE /news/audit-1/                           3->33  10->33  flat
PROBE /search/?q=审计                            3->62  10->62  flat
PROBE /me/registrations/                       3->9  10->9  flat
PROBE /me/scrims/                              3->9  10->9  flat
PROBE /calendar/<签名>.ics                     3->19  10->19  flat
PROBE /teams/36/                               3->23  10->22  flat
PROBE /admin/activity/                         3->18  10->18  flat
```

## 本轮范围

在 `test_chapter15_audit.py` 里用已有的 `assert_no_n_plus_one` 给资讯列表、首页、文章评论、站内搜索、我的报名、我的内战、日历订阅、战队主页各加一条。只加测试，不改页面代码。

（写测试时补：探测时搜索只放了战队；守卫里放了文章以后，搜索每多一篇命中的文章多 2 次查询。这是守卫要抓的东西，本轮一起修。）

## 验证

每条测试对应去掉页面上的一处 `select_related`，确认会红（变异脚本）。

## 验收标准

测试机上整组检查全绿；变异全部被抓到；推送 `main`，CI 绿。
