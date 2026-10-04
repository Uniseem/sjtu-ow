# 175 两条会随机失败的测试改准（报告）

## 做了什么

1. `scrims/tests/test_teaming.py`、`tournaments/tests/test_adhoc_teams.py`：`assert "cdn" not in html.lower()` 改成 `assert not re.search(r'<(script|link)[^>]+(src|href)="(https?:)?//', html)`
2. 173 的 `report.md`、`review.md`：在「停用时不撤回申请」那两处下面加「175 轮更正」：后台编辑页停用时本来就调 `after_deactivation` 撤回（设计 3.7），173 的测试直接改 `is_active`、绕过了它；173 的拦截给没走编辑页的停用路径兜底
3. AGENTS.md：别用一个短词断言页面里「没有」某样东西

## 怎么发现的

174 推送后 `gh run list` 看到 171 那次是红的：

```
completed	failure	171: 网站图标补齐，favicon.ico 和主屏幕图标（设计 v6.55）	CI	main	push	37178928546	3m30s
```

日志：

```
>       assert "cdn" not in html.lower()
FAILED scrims/tests/test_teaming.py::test_the_board_carries_what_the_capacity_rule_needs - assert 'cdn' not in '<!doctype h...>\n</html>\n'
```

171 改的是图标，和这个页面无关；172、173 用同样的代码都是绿的。页面里唯一每次不同的就是随机令牌。**171 推送后我没有等到 CI 跑完再看**，这一轮才发现。

## 命令输出

变异（测试机，2 处，全部被抓到）：

```
baseline green, 2 tests
caught split page script from a CDN -> test_the_board_carries_what_the_capacity_rule_needs
caught teams page stylesheet from a CDN -> test_the_board_carries_what_the_script_and_the_view_need
restored and green; missed: none
```

整组检查（测试机）：

```
1645 条测试分成 4 片
分片 1：412 passed in 38.35s
分片 2：411 passed in 38.07s
分片 3：411 passed in 42.84s
分片 4：411 passed in 39.31s
== 全部通过 (05:41:00)
```

只改了测试和文档，演示站推送后 `git pull`。
