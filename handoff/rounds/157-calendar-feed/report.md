# 157 「我的报名」可以订阅到手机日历（报告）

## 做了什么

1. `core/calendar_feed.py`（新）：`token()` / `user_for()`（签名，盐 `sjtu-ow.calendar`，只认在用的账号）、`feed_url()`（`https://` 和 `webcal://` 两种）、`_escape()`（RFC 5545 的反斜杠、分号、逗号、换行）、`_fold()`（超过 75 字节的行折到下一行、开头一个空格，不拆开汉字）、`ics()`
2. `core.agenda.items_for()` 加 `limit` 参数（首页还是 4 条，日历传 `None` 不限）
3. `core/views.calendar_feed` + 地址 `/calendar/<签名>.ics`：每个 IP 每分钟 30 次，超了 429；签名不对或账号停用 404；`text/calendar`，`Cache-Control: private, max-age=900`，`X-Robots-Tag: noindex`
4. `content.models.RESERVED_CHILD_SLUGS` 加 `calendar`（见下）
5. 「我的报名」页最后「订阅到手机日历」：`webcal://` 按钮、`https://` 地址、别外传的提醒
6. 设计 v6.49（13.5）；README「报名」
7. `core/tests/test_calendar_feed.py`（6 条）

## 已有测试拦下的

第一次整组检查 `test_every_fixed_top_level_route_is_reserved` 红了：新加的第一段路径 `calendar` 不在保留的网址片段里，编辑在首页下建一个 slug 是 calendar 的页面会被这个地址盖住（078 加的守卫）。加进保留列表；演示站上查过没有这个 slug 的页面。

## 自查改掉的

报告第一稿的「没做」里写了一句「长行不折行各家日历也都能读」，这句没验证过；而且长行很常见：说明里分队加网址、赛事报名详情的网址都超过 75 字节。改成按 RFC 5545 3.1 折行，测试检查每一行不超过 75 字节、去掉折行后内容不变；内战测试的标题改长，让真实输出里一定有折行。

## 命令输出

变异（测试机，加折行之后 9 处，全部被抓到）：

```
baseline green, 6 tests
caught scrims last two hours -> test_my_scrims_become_calendar_events
caught undated events go in -> test_my_scrims_become_calendar_events
caught no team in the description -> test_my_scrims_become_calendar_events
caught commas left as they are -> test_text_is_escaped
caught long lines not folded -> test_my_scrims_become_calendar_events
caught folds split characters -> test_long_lines_are_folded_without_splitting_characters
caught deactivated accounts keep their calendar -> test_a_bad_or_dead_address_is_not_found
caught no rate limit -> test_hammering_the_feed_is_limited
caught the page does not offer it -> test_my_registrations_page_offers_it
restored and green; missed: none
```

整组检查（测试机，加了保留片段和折行之后）：

```
1594 条测试分成 4 片
分片 1：399 passed in 35.61s
分片 2：399 passed in 37.12s
分片 3：398 passed in 34.65s
分片 4：398 passed in 33.79s
== 迁移 (00:36:04)
No changes detected
== 生产配置 (00:36:05)
System check identified no issues (0 silenced).
== 错误页和模板一致 (00:36:06)
== Docker 镜像 (00:36:07)
构建成功：fa1ec08c441d
== 全部通过 (00:36:07)
```

`docs/design-details.md`（补 156 漏写的首页「我的安排」和本轮的日历）是在上一次整组检查之后改的，读这份文档的 14 个测试文件当时在测试机上重跑过：`284 passed in 27.46s`；上面这次整组检查已经包含它。

演示站升级后，在服务器上挑了报名最多的演示用户，用公网域名取这个用户的日历（经用户的反向代理，HTTPS）：

```
HTTP/2 200
cache-control: private, max-age=900
content-type: text/calendar; charset=utf-8
x-robots-tag: noindex

BEGIN:VCALENDAR
...
X-WR-CALNAME:咩咩 的社团安排
BEGIN:VEVENT
UID:scrims-2@sjtu.ow-shanghaiuniversity.com
DTSTART:20261005T113000Z
DTEND:20261005T143000Z
SUMMARY:内战：国庆特别场 · 6v6 怀旧
DESCRIPTION:已报名\nhttps://sjtu.ow-shanghaiuniversity.com/scrims/2/
...
```

## 顺带补的文档

`docs/design-details.md` 第 7 节（首页）156 轮没写「我的安排」，本轮补上；第 9 节「我的报名」加日历一块。

## 没做 / 未验证

- **没在真手机上订阅过**（未验证）：测试机没有 iOS / Android 日历。格式按 RFC 5545 写（CRLF 行尾、转义、75 字节折行、UTC 时间）
- 没做「重置地址」（见复核）
