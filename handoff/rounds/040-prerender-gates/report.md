# 040 实现报告

## 结论

**完成了 039 三个空白里的第一个**（最严重的那个）。另外两个没做——用户让停，剩下的记在 STATUS 里。

## 做了什么

给 `core/prerender.py` 的安全闸补了 3 条测试：

| 测试 | 验什么 |
|---|---|
| `test_a_response_that_sets_a_cookie_is_never_frozen` | 响应带 Set-Cookie 时拒绝写静态文件，错误信息点名是哪个 cookie |
| `test_a_page_leaking_a_secret_marker_is_never_frozen` | 正文命中 `SECRET_MARKERS` 时拒绝 |
| `test_a_clean_public_page_is_frozen` | **普通页面不能被误拒**——否则闸再严也没用，等于关掉了预渲染 |

第三条是故意加的：只测「该拒的拒了」，一个永远返回拒绝的实现也能通过。

## 为什么原来测不到

023 轮有一条 `test_a_prerendered_page_has_no_csrf_token_or_personal_data`，看名字像是覆盖了。但它验的是**生成出来的 HTML 里没有敏感内容**，不是**该拒绝的响应被拒绝了**。

首页本来就不设 cookie，所以那条测试**永远走不到这道闸**。闸拆掉它照样绿。

这三条用 `monkeypatch` 直接替换 `Client.get` 的返回，构造出「设了 cookie 的响应」「正文含敏感标记的响应」——不然没有真实页面能触发它们。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
209 files already formatted

$ uv run python -m pytest -q
650 passed in 51.23s
```

## 剩下的两个空白

039 找到的另外两个没动：

1. **签名比对没断言用 `compare_digest`**（017）。改成 `==` 全部测试照过。
2. **解散战队的 `is_disbanded` 检查没测试**（012）。`teams/services.py` 里有 4 处。

细节在 `rounds/039-mutation-sweep/report.md`，STATUS 里也记着。

## 改动文件

```
core/tests/test_prerender.py   新增 3 个测试
```
