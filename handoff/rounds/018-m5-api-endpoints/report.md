# 018 实现报告

> 本轮由实现方（Claude）自己做，用户外出。下面所有输出都是真实跑出来的；没跑的会写「未验证」。

## 结论

**完成。** 开放 API 的 11 个业务接口全部实现并用真实签名打通。实现过程中发现设计 8.5 和 11.6.7 有三条规则在 014–016 的状态机里没有落实（上游在本站审核模式下能改状态、两级审核能被上游跳过、审核不幂等），已一并修掉——这三条都不是新代码引入的，是之前几轮留下的洞，本轮因为要按 11.6.7 的表逐格验收才暴露出来。

## 逐条结果

### T1 两个外键

`Tournament.source_client`、`RegistrationStatusLog.actor_client` 指向 `integrations.ApiClient`，唯一约束改成 `(source_client, external_id)`，迁移 `tournaments/migrations/0004_tournament_source_client_and_more.py`。

### T2 序列化与分页

- `integrations/serializers.py`：赛事、战队、名单成员、状态日志、报名五种对象；`apply_fields()` 支持 `team.name` 这样的点号路径，字段名不存在抛 `invalid_field`；`external_id` 只对推送它的那个客户端可见。
- `integrations/pagination.py`：游标是 base64 的 `{"u": updated_at, "i": id}`，按 `updated_at, id` 排序，`limit` 默认 50 上限 200，支持 `updated_since`。
- `integrations/sanitize.py`：白名单 HTMLParser，`script` / `style` 连内容一起丢掉。

### T3–T5 接口

11 个接口见 README「开放 API → 业务接口」表。本站草稿对上游不可见，上游自己推的赛事无论什么状态都能看到自己那份。

### T6 审核

`perform_review()` 按 11.6.7 的表做：动作合法性 → `roster_version` 必填 → 版本比对（409）→ 审核模式（403）→ 幂等短路 → 交给状态机。状态机的错误按 `RegistrationError.code` 映射成 403 / 409 / 400。

### T7 操作方记录

`_stamp_client()` 把客户端写到最新那条上游日志上。日志接口本身**不返回** `actor_user` 和 `actor_client`，只给 `actor_type`。

## 验收输出

### 1. 检查与测试

```
$ ruff check .
All checks passed!

$ ruff format --check .
233 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ uv run python -m pytest -q
371 passed in 24.87s

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

> `check --deploy` 一开始被我自己写的 018 视图弄脏了 5 条警告：两对列表/详情接口的 `operationId` 撞车（W001），三个 POST/PUT 视图猜不出请求序列化器（W002）。已经给 11 个视图都加了显式 `operation_id`，给三个写接口加了 `request=OpenApiTypes.OBJECT`。

本轮新增 26 个测试（`integrations/tests/test_api_endpoints.py`）。

### 2. 用真实签名把全部接口打一遍

起了真实 dev server（`127.0.0.1:8018`），用独立脚本按设计 11.2.2 算签名，走真实 HTTP。

赛事列表：

```
=== GET /api/v1/tournaments -> 200
{"data": [{"id": 3, "source": "local", "external_id": null, "title": "018 验证赛事",
  "status": "published", "roster_min": 2, "roster_max": 5, "review_mode": "upstream",
  "url": "http://localhost:8000/tournaments/3/", ...}],
 "next_cursor": null, "has_more": false}
```

按上游 ID 创建（注意 `<script>` 被清掉、`<b>` 保留）：

```
=== PUT /api/v1/tournaments/external/verify-018 -> 201
{"data": {"id": 4, "source": "upstream", "external_id": "verify-018",
  "title": "上游推送的验证赛事",
  "description_html": "<p>说明<b>加粗</b></p>", ...}}
```

`fields` 裁剪（`id` 自动保留）：

```
=== GET /api/v1/registrations?include=team&fields=status,roster_version,team.name -> 200
{"data": [{"id": 4, "status": "pending", "roster_version": 1,
           "team": {"id": 6, "name": "018 验证战队"}}]}
```

字段名写错：

```
=== GET /api/v1/registrations?fields=no_such_field -> 400
{"error": {"code": "invalid_field", "message": "没有字段「no_such_field」",
           "details": {"field": "no_such_field"}}}
```

状态日志（只有 `actor_type`，没有管理员身份）：

```
=== GET /api/v1/registrations/4/logs -> 200
{"data": [
  {"id": 9,  "from_status": null,      "to_status": "pending",  "action": "submit",  "actor_type": "captain",  "roster_version": 1},
  {"id": 10, "from_status": "pending", "to_status": "approved", "action": "approve", "actor_type": "upstream", "roster_version": 1}]}
```

统计：

```
=== GET /api/v1/tournaments/3/stats -> 200
{"data": {"tournament_id": 3,
  "registrations_by_status": {"pending": 0, "awaiting_upstream": 0, "approved": 1, "rejected": 0, "withdrawn": 0},
  "active_members": 2, "active_sjtu_members": 1, "active_non_sjtu_members": 1}}
```

### 3. CSV 前几行

不带展开（第一行有 BOM，Excel 打开不乱码）：

```
registration_id,status,roster_version,team_id,team_name,user_id,nickname,battletag,is_sjtu,is_captain
4,approved,1,6,018 验证战队,35,验证队长,验证队长#1234,true,true
4,approved,1,6,018 验证战队,36,验证队员甲,验证队员甲#1234,false,false
```

带 `include=members.ranks` 时多三列：

```
registration_id,status,roster_version,team_id,team_name,user_id,nickname,battletag,is_sjtu,is_captain,rank_tank,rank_damage,rank_support
4,approved,1,6,018 验证战队,35,验证队长,验证队长#1234,true,true,未定级,钻石 3,未定级
4,approved,1,6,018 验证战队,36,验证队员甲,验证队员甲#1234,false,false,未定级,前 500,未定级
```

### 4. 名单版本不匹配 + 批量审核部分失败

```
=== POST /api/v1/registrations/4/review -> 409
{"error": {"code": "roster_version_mismatch",
           "message": "名单已被队长更新，请重新获取后再审核",
           "details": {"current_roster_version": 1}}}
```

批量三条：一条成功、一条不存在、一条版本不对，整体仍是 200：

```
=== POST /api/v1/registrations/review-batch -> 200
{"data": [
  {"id": 4,      "ok": true,  "registration": {"id": 4, "status": "approved"}},
  {"id": 999999, "ok": false, "error": {"code": "not_found", "message": "报名不存在"}},
  {"id": 4,      "ok": false, "error": {"code": "roster_version_mismatch",
                                        "message": "名单已被队长更新，请重新获取后再审核",
                                        "details": {"current_roster_version": 1}}}]}
```

### 5. 幂等（设计 11.6.7）

验证脚本跑了 3 遍，每遍发 2 个 approve（批量里一个、单条一个），一共 **6 次通过请求**。事后查库：

```
status approved logs 2
  9  submit  None    -> pending  captain  client= None
  10 approve pending -> approved upstream client= 3
```

只有一条 approve 日志，`updated_at` 也没被后面几次刷新。`actor_client` 记到了客户端 3。

### 6. 本站审核模式下上游不能改状态

把赛事改成 `local` 之后：

```
=== POST /api/v1/registrations/4/review -> 403
{"error": {"code": "review_not_allowed", "message": "这项赛事由本站审核，上游不能改状态"}}
```

### 7. 联系方式不外泄

六个接口（报名列表带全部展开、报名详情、日志、名单、CSV、统计）的真实响应里检索 `987654321`（QQ）、`@example.com`（邮箱）、`argon2`（密码散列）：

```
泄漏结果: 无
```

### 8. 调用日志

```
200 GET  /api/v1/tournaments/3/stats                            -                    7ms
200 GET  /api/v1/tournaments/3/roster.csv?include=members.ranks -                    2ms
403 POST /api/v1/registrations/4/review                         review_not_allowed   2ms
```

### 9. 回归 + docker / caddy

```
$ uv run python -m pytest -q
371 passed in 24.87s

$ docker build -t sjtu-ow:018 .
sha256:50c16316468a498295253e995674fde67aa9879c0fe60d14dc023a37d01401d2

$ docker run --rm -v ./deploy:/etc/caddy:ro caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile
Valid configuration
```

### 10. 清理

本轮验证数据全部删除：赛事 2 个、报名 1 条、战队 1 个、账号 2 个、API 客户端 1 个、调用日志 56 条。

清理时发现**004–007 轮的验证数据一直没删干净**：9 个 `@example.com` 账号和 6 篇验收用的文章页（`M2 验收攻略`、`B站嵌入验收`、`007 投稿稿件` 等）还在库里，账号还被文章的 `author`（PROTECT）拴着删不掉。已经一并删除。现在库里只剩正常骨架：Root / 首页 / 资讯 / 用户协议 / 隐私政策 / 关于我们，加 5 个文章分类，`User` 和 `ArticlePage` 都是 0。

## 设计偏差

**没有改设计文档。** 三点说明：

1. **`review_not_allowed` 和 `invalid_state_transition` 两个错误码**是设计 11.6.7 明确要求的（「`local` | 任何 | 任何 | 返回 `403 review_not_allowed`」「其他组合返回 `409 invalid_state_transition`」），但 11.4 的错误码总表里没列。我按 11.6.7 的正文实现了，总表算漏写。**要不要把这两个码补进 11.4 的表，请用户定。**
2. **幂等的判定口径**：设计说「已经是这个操作的目标状态，并且名单版本一致」。`reject` 和 `revoke` 的目标状态都是 `rejected`，所以对一条已驳回的报名再调 `revoke` 也会走幂等。这符合字面规则，但语义上是两个动作合到了一格。
3. **`roster_version` 传非整数**返回 `400 validation_error`，设计没写这一格。

## 未完成 / 不同意

1. **Webhook 投递与重试**、**接口文档页面**、**日志清理任务**是 019。
2. 报名列表目前对所有持 `registrations:read` 的客户端一视同仁，不按「只能看自己推送的赛事的报名」过滤——设计 11.6.4 的筛选参数里没有这条限制，先按设计做。**如果实际上应该限制，这是个要确认的口子**（见下）。

## 顺带发现

1. 设计 8.5 的三条规则在 014–016 的状态机里只做了一半：只挡本站管理员，没挡上游。详见 `review.md`。
2. drf-spectacular 的 `operationId` 是按路径推的，`/tournaments` 和 `/tournaments/{id}` 会推出同一个名字，必须显式给 `operation_id`。

## 需要确认

1. **持 `registrations:read` 的上游能不能看到别的上游推送的赛事、以及本站自办赛事的报名和名单？** 现在能。设计 11.6.4 没写限制，但从数据最小化角度看更像是应该按 `source_client` 过滤。这条影响面比较大，等你回来定。
2. `review_not_allowed` / `invalid_state_transition` 是否补进设计 11.4 的错误码总表。

## 改动文件

```
tournaments/registration.py            上游审核模式守卫、错误码、两级审核不能被跳过
integrations/api.py                    两个错误码
integrations/api_views.py              11 个接口、幂等、错误映射、operation_id
integrations/serializers.py            新增
integrations/pagination.py             新增
integrations/sanitize.py               新增
integrations/urls.py                   路由
integrations/tests/test_api_endpoints.py  新增 26 个测试
tournaments/models.py                  两个外键 + 唯一约束
tournaments/migrations/0004_*.py       新增
README.md                              业务接口一节
```
