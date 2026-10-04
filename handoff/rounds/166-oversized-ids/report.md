# 166 地址里的编号太大、日期太离谱时返回 404 或提示，不再 500（报告）

## 做了什么

1. `core/converters.py`（新）：`IdConverter`，`[0-9]{1,18}`；`core/apps.py` 的 `ready()` 里注册成 `id`（在读任何 URLconf 之前）
2. 项目自己的 11 个文件里 59 处 `<int:…>` 换成 `<id:…>`（前台的 urls 和后台用钩子注册的地址）
3. `core/activity.py`：起止日期限定在 2000-01-01 到 2100-12-31，超出时「日期只能在 2000 年到 2100 年之间，下面是本学年的数据」
4. `core/tests/test_oversized_ids.py`（3 条）：两个 20 位编号的地址 404、18 位的还能到视图；离谱日期给提示、边界日期可以；项目代码里没有 `<int:`

## 怎么发现的

165 之后临时写了一个探测（没提交）：匿名、成员、超级管理员三种身份访问 42 个带奇怪参数的地址，只看有没有 500。39 个是 200、302、404、405，三个 500：

```
PROBE 500 /admin/activity/?start=0001-01-01&end=9999-12-31
PROBE 500 /admin/announce/article/99999999999999999999/
BAD [('/admin/activity/?start=0001-01-01&end=9999-12-31', 500), ('/admin/announce/article/99999999999999999999/', 500)]
```

接着按同样的原因找到公开的 `/comments/<文章编号>/more/`（`comments/services.py` 按文章编号取文章）：

```
STATUS /comments/99999999999999999999/more/ 500
STATUS /admin/announce/scrim/99999999999999999999/ 404
```

内战是 404、文章是 500：Django 对普通主键的超范围查询直接当作没有，文章的主键是 Wagtail 页面的一对一外键，这层保护不管，SQLite 报 `OverflowError`。

## 命令输出

变异（测试机，6 处，全部被抓到）：

```
baseline green, 3 tests
caught ids of any length -> test_a_huge_article_number_is_not_found
caught the longest id refused -> test_a_huge_article_number_is_not_found
caught comments back on int -> test_a_huge_article_number_is_not_found
caught comments back on int -> test_no_address_takes_numbers_of_any_length
caught announce back on int -> test_no_address_takes_numbers_of_any_length
caught no date range -> test_dates_past_any_calendar_get_a_word
caught 1999 allowed -> test_dates_past_any_calendar_get_a_word
restored and green; missed: none
```

整组检查（测试机）：

```
1623 条测试分成 4 片
分片 1：406 passed in 37.02s
分片 2：406 passed in 37.22s
分片 3：406 passed in 36.19s
分片 4：405 passed in 37.25s
== 全部通过 (02:48:23)
```

演示站升级后从公网访问：

```
404 /comments/99999999999999999999/more/
404 /comments/1/more/
200 /scrims/7/
200 /members/1/
200 /comments/17/more/
```

（1 号页面不是文章，本来就是 404；17 号是有评论的文章，「加载更多」照常。）

## 没做

- Wagtail 自己的后台地址（比如 `/admin/pages/<编号>/edit/`）用的是它的路由，没改
