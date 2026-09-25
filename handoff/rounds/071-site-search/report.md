# 071 实现报告

## 结论

**完成。** 设计 v1.8 新增 13.16 节；新应用 `search` 提供文章、赛事与内战、战队、成员四类的子串搜索，页头有搜索框，`/search/` 实时渲染并限流。16 条测试，9/9 处规则变异被抓到。

## 逐条结果

| 任务 | 结果 |
|---|---|
| 设计 v1.8 | 1.3 把站内搜索从「不做」拿掉；2.3 加 `search` 应用；13.4 加 `/search/`；新增 13.16 节（入口、匹配规则、四类范围表、不搜什么、结果形态、限流、robots、正文为什么在应用层匹配）；13.14 的 robots 说明顺手去掉 067 遗留的 `/api/`、加 `/search/`；15.2 一行；附录 C 两行；附录 D |
| `search/services.py` | `parse_query()`（截 50 字、按空白拆词、最多 5 个、casefold）、`matches()`（每个词都命中）、`excerpt()`（首次命中前后各 40 字，去标签）、四个提供方各返回一个 `Group`（最多 20 条，多出来标 `truncated`）。**全部在应用层匹配**：`ArticlePage.body` 是 StreamField，Django 的 JSONField 存盘时 `ensure_ascii`，中文变成 `\uXXXX`，数据库 `icontains` 对正文无效；其他三类量小，统一处理 |
| 范围 | 文章：`live().public()`；赛事：已发布和已结束；内战：已发布和已结束；战队：未解散；成员：`members.services.joined_users()`。不搜草稿、已取消、已解散、停用或未验证邮箱的人；不搜游戏 ID、联系方式、邮箱 |
| 视图与页面 | `/search/?q=`：空词只显示搜索框；每 IP 每分钟 30 次，超过渲染 `errors/429.html`；结果按类型分组，每组带数量和摘录，超 20 条提示换词。`templates/base.html` 顶栏加 GET 搜索框（无 CSRF，预渲染页可含）；`robots.txt` 加 `Disallow: /search/` |
| 测试 | `search/tests/test_search.py` 16 条：解析与截断、摘录两条、多词交集、文章三处字段命中与摘录去标签、未发布不搜、赛事与内战的范围、战队排除已解散、成员排除停用、每类截到 20、页面四种状态（空、分组、没找到、429）、页头搜索框、超长词截断；附录 C pin 加 5 个常量；地址清单加 `/search/`；robots 测试加 `/search/` |

## 验收输出

```
$ uv run python manage.py tailwind build --force
Built production stylesheet 'C:\Users\fyc12\Desktop\Claudee\sjtu-ow\static\css\app.css'.

$ uv run ruff format . && uv run ruff check .
1 file reformatted, 227 files left unchanged
All checks passed!

$ PYTHONUTF8=1 uv run pytest -q search
16 passed in 3.05s

$ PYTHONUTF8=1 uv run pytest -q
828 passed in 125.47s (0:02:05)
```

**变异（脚本 `mutate_071.py`，本轮目录）**

```
✓ 被抓到 未发布文章也搜 | 2 failed, 14 passed in 3.38s
✓ 被抓到 草稿和取消的赛事也搜 | 1 failed, 15 passed in 3.50s
✓ 被抓到 草稿内战也搜 | 1 failed, 15 passed in 3.42s
✓ 被抓到 已解散的战队也搜 | 1 failed, 15 passed in 4.79s
✓ 被抓到 成员不再限于成员页上的人 | 1 failed, 15 passed in 5.27s
✓ 被抓到 每类不再截到 20 条 | 1 failed, 15 passed in 5.39s
✓ 被抓到 只要一个词命中就算 | 1 failed, 15 passed in 5.27s
✓ 被抓到 搜索词不再截断 | 1 failed, 15 passed in 5.46s
✓ 被抓到 限流被拆掉 | 1 failed, 15 passed in 5.54s
---
9/9 mutations caught
```

## 设计偏差

无。用户说「纯 ORM icontains」是我在计划里写的实现设想，做的时候发现对 StreamField 正文无效，改成应用层匹配，写进 13.16 节。

## 未完成 / 顺带发现

- 结果按更新时间倒序，没有相关度排序（本轮范围明确不做）
- 文章正文搜索每次把全部已发布文章渲染成文本，几百篇以内没问题；13.16 写了什么时候该改成索引
- 页头搜索框只放在顶栏，没有进手机端的抽屉导航；顶栏在所有尺寸都显示，先这样
- 搜索框的样式没在浏览器里看过（顶栏是深色底，输入框用了 `text-base-content`），074 部署后看一眼

## 需要确认

无。

## 改动文件

`docs/design.md`、`README.md`、`AGENTS.md`、`handoff/STATUS.md`、`handoff/rounds/071-site-search/`；`search/`（新：`__init__.py`、`apps.py`、`services.py`、`views.py`、`urls.py`、`templates/search/results.html`、`tests/`）；`sjtu_ow/settings/base.py`、`sjtu_ow/urls.py`、`pyproject.toml`；`templates/base.html`；`content/views.py`、`content/tests/test_content.py`；`core/tests/test_chapter15_audit.py`、`core/tests/test_documented_urls.py`
