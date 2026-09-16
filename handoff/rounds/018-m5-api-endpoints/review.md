# 018 复核结果

> 实现方自查（用户外出）。等用户回来，008–018 可以一起交给 Grok 做独立复核。

## 结论

**通过。** 自查中发现并修掉 **3 个真实的状态机漏洞**（都不是本轮新写的代码，是 014–016 留下的）、**5 条会污染 `check --deploy` 的警告**（本轮引入）、**1 个我自己写的假测试**，另外清掉了 004–007 轮遗留的验证数据。

自查方式和前几轮一致：不看自己写的 `report.md`，拿设计 8.5 和 11.6.7 的表逐格对照代码，再用真实签名打真实服务。

## 验证记录

| 验证 | 方法 | 结果 |
|---|---|---|
| 检查与测试 | `ruff`、`pytest`、`makemigrations --check`、生产 `check --deploy` | 371 passed，部署检查干净 |
| 全部接口 | 真实 dev server + 按 11.2.2 自己算签名，走真实 HTTP | 11 个接口全部 200/201 |
| 审核模式矩阵 | 按 11.6.7 的表逐格构造 | `local`→403、两级跳级→409、正常→200 |
| 幂等 | 同一个 approve 真实发 6 次 | 库里只有 1 条 approve 日志 |
| 名单版本 | 传 99 | `409 roster_version_mismatch`，details 带当前版本 |
| 批量部分失败 | 成功 / 不存在 / 版本不对 三条 | 整体 200，逐条成败独立 |
| 联系方式 | 六个接口的真实响应里搜 QQ / 邮箱 / 密码散列 | 无 |
| 日志身份 | 日志接口响应 | 只有 `actor_type`，无 `actor_user` / `actor_client` |
| CSV | 真实下载 | 带 BOM，`include` 决定是否有段位三列 |
| 容器 | `docker build`、`caddy validate` | 都通过 |
| 清理 | 查库 | `User` 0、`ArticlePage` 0、`ApiClient` 0、`Tournament` 0 |

## 自查中发现并已修掉

### A1 上游在「本站审核」模式下能改状态（设计 8.5，严重）

`tournaments/registration.py` 的 `approve()` / `reject()` 只挡了本站管理员：

```python
if actor_type == ActorType.ADMIN and not local_review_allowed(tournament):
    raise RegistrationError("这项赛事由上游审核，本站不能改状态")
```

反方向没有守卫。设计 8.5 写得很清楚：「本站审核 `local`｜赛事管理员在后台审核，**上游不能改状态**」。也就是说任何一个拿到 `registrations:review` 的上游，都能去审核本站自办赛事的报名——包括别的上游推的赛事。

加了对称的 `upstream_review_allowed()` 和统一的 `_guard_actor()`。

### A2 两级审核能被上游跳过（设计 8.5，严重）

原来 `approve()` 里：

```python
two_stage_local = (tournament.review_mode == TWO_STAGE and actor_type == ADMIN)
to_status = AWAITING_UPSTREAM if two_stage_local else APPROVED
```

上游对一条 `pending` 调 approve，`two_stage_local` 是 False，于是**直接变成 `approved`**，本站这一级审核被整个绕过。设计 8.5 的状态表里，`pending → awaiting → approved` 是两步，上游只能做第二步。

改成：两级审核模式下上游碰 `pending` 直接报错，走 `409 invalid_state_transition`。

### A3 审核不幂等（设计 11.6.7）

设计明确写了「上游网络超时重试时不会产生副作用」。原来对一条已通过的报名再调 approve，状态机抛「当前状态不能通过」，返回 400。上游超时重试就会拿到假的失败，然后很可能去人工干预。

在 `perform_review()` 里加了短路：版本一致且已经是目标状态就直接返回成功，不写日志不发通知。用真实 HTTP 发 6 次 approve 验证，日志只有 1 条。

### A4 错误码全部压成了 400（设计 11.6.7）

原来 `except RegistrationError: raise ApiError("validation_error", ...)`，把「模式不允许」「状态不对」「缺备注」三种情况都变成 400。设计要求分别是 403 / 409（带 `details.current_status`）/ 400。

给 `RegistrationError` 加了 `code`，在 API 层映射。

### A5 我自己写了一个什么都没断言的测试

第一版 `test_local_mode_rejects_upstream_review` 长这样：

```python
assert registration.status == RegistrationStatus.APPROVED or response.status_code
assert registration.logs.filter(actor_type="upstream").exists() is (response.status_code == 200)
```

两行都恒真——我当时不确定正确行为是什么，就写了个跟着实现走的断言，它 22 个测试一次全绿里也混过去了。**这种测试比没有测试更坏**：它会把 A1 这样的洞盖住，还让人以为覆盖到了。查了设计 8.5 确认正确行为之后重写成真断言（403 + 状态不变 + 无上游日志），它立刻就红了，这才暴露出 A1。

记一条给自己：**先去设计文档里确认期望行为，再写断言。不确定就先查，不要写「跟着当前实现走」的断言。**

### A6 本轮把 `check --deploy` 弄脏了 5 条

两对列表/详情接口 `operationId` 撞车，三个写接口猜不出序列化器。017 的验收标准是部署检查必须干净，我差点带着 5 条警告交出去。已给 11 个视图加显式 `operation_id`、三个写接口加 `request=`。

### A7 004–007 轮的验证数据一直没删

9 个测试账号 + 6 篇验收文章页还在库里，还互相 PROTECT 拴着。前几轮的 report 都写了「已清理」，实际上没清干净。已删除，现在库里只剩正常骨架。

**这说明「清理」这一步之前只清了当轮新建的东西，没有回头查库。以后每轮清理后应该查一次全库计数，而不是只删自己记得的那几条。**

## 建议修（转 019 或等用户定）

1. **报名的可见范围**（较重要）：现在任何持 `registrations:read` 的客户端都能看到全站所有赛事的报名和名单，包括本站自办的和别的上游推的。设计 11.6.4 没写限制，所以实现上没加，但从数据最小化的角度这像是个口子。等用户定：是按 `source_client` 过滤，还是在客户端上加一个「可见赛事范围」的配置。
2. **设计 11.4 的错误码总表**漏了 `review_not_allowed` 和 `invalid_state_transition`，11.6.7 的正文里有。建议补表。
3. **`revoke` 对已驳回的报名会走幂等**：因为 `reject` 和 `revoke` 的目标状态都是 `rejected`。符合设计字面，但语义上把两个动作合到了一格，值得在文档里写明。

## 认可的判断

1. `external_id` 按 `(source_client, external_id)` 唯一、且只对推送它的客户端可见——设计 11.6.3 要求的「不同上游可以使用相同的 ID，互不影响」落实到位了。
2. 白名单清洗 `description_html`，而不是黑名单过滤 `<script>`。
3. CSV 带 BOM。
4. 批量审核逐条 `transaction.atomic()`，一条失败不影响别的。
5. 日志接口不返回管理员身份，只给 `actor_type`——设计 12.8.4 要求的最小暴露。

## 文档更新

- `docs/design.md` 本轮**没有改动**（两条建议补充见上，等用户定）。
- `README.md` 加了「开放 API → 业务接口」一节。
- `handoff/STATUS.md` 轮次表加 018，`next: claude`。
