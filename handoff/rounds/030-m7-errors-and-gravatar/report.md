# 030 实现报告

## 结论

**完成。** gravatar 关掉了。错误码那件事——我 018 轮的说法是错的，而且真查下去发现了**五处不符**，都修了。

## 先更正我自己的错误

018 轮我在 report 和 STATUS 里写：

> **设计 11.4 的错误码总表**漏了 `review_not_allowed` 和 `invalid_state_transition`（11.6.7 正文里有），要不要补表？

**这条是错的。** 错误码总表在 **11.10** 不是 11.4（11.4 是「通用参数」），而且那两个码**本来就在表里**：

```
| 403 | `review_not_allowed`       | 这个赛事的审核模式不允许上游审核 |
| 409 | `invalid_state_transition` | 当前状态不允许这个操作 |
```

我当时没找到表，就认定表里没有，还把它挂成了一个要用户拍板的问题，占了两轮 STATUS。**看错章节号这种事，代价是别人替我背了一个不存在的问题。**

## 真正的不符（五处）

把 11.10 的 19 个码和实现比对：

```
设计有、实现没有：
  ❗ invalid_request            设计 400
  ❗ invalid_include            设计 400
  ❗ invalid_cursor             设计 400
  ❗ internal_error             设计 500

状态码不一致：
  ❗ validation_error           实现 400  设计 422

实现有、设计没有：（无）
```

### 逐条处理

**`validation_error` 400 → 422**。设计写的是 422，实现一直返回 400。改了实现，同时改了四条断言 400 的测试。

**`invalid_include`（400）**。设计把两件事分开：
- `400 invalid_include` —— 这个展开项**不存在**（打错字）
- `403 include_not_allowed` —— 展开项存在，但这个客户端**没权限**

实现把两种都当成 403。对上游来说差别很大：拼错 `menbers` 却被告知「没有权限」，会让人去查授权配置而不是查拼写。改成先查名字是否存在，`details` 里带上全部合法取值。

**`invalid_cursor`（400）**。游标坏掉原本返回 `validation_error`，改成专用码。

**`invalid_request`（400）**。JSON 解析不了原本落到 `validation_error`，现在识别 DRF 的 `ParseError`。

**`internal_error`（500）**。原本未被 DRF 处理的异常直接抛给 Django，返回 HTML 错误页——对一个 JSON API 是错的。现在兜住，返回信封并带上 `X-Request-Id`。

## 修的过程中差点弄出个更大的问题

第一版我在 `exception_handler` 里写了：

```python
response.status_code = ERRORS[code][0]
```

想法是「让状态码和错误码表一致」。结果**把 DRF 自己判断出来的状态码盖掉了**：匿名访问 `/api/v1/docs/` 从 403 变成了 422。

两条 019 轮写的测试立刻红了：

```
FAILED test_docs_page_is_closed_to_anonymous_visitors
FAILED test_docs_page_is_closed_to_a_normal_staff_member
```

**这次是测试救了我**，而且救的是我这轮新写的代码。改成只填错误码名字、状态码一律听 DRF 的。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
205 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ uv run python -m pytest -q
588 passed in 41.74s

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

新增 7 个测试，其中一条把整张 19 行的错误码表（码名 + 状态码）钉死。

## T1 关闭 gravatar

```python
WAGTAIL_GRAVATAR_PROVIDER_URL = None
```

理由（020 轮记的）：后台 CSP 不允许外部图片，头像一直是空的；而且查一次 gravatar 等于把管理员邮箱的哈希发给第三方，和隐私政策的口径不一致。

加了测试：断言设置为 `None`，并且真的访问一次 `/admin/` 确认正文里不出现 `gravatar`。

## 改动文件

```
integrations/api.py                      4 个新错误码、validation_error 改 422、
                                         invalid_include 与 include_not_allowed 分开、
                                         exception_handler 兜住未处理异常且不改状态码
integrations/pagination.py               游标错误用 invalid_cursor
integrations/tests/test_api_endpoints.py 7 个新测试；4 条 400 改 422
sjtu_ow/settings/base.py                 WAGTAIL_GRAVATAR_PROVIDER_URL = None
core/tests/test_chapter15_audit.py       gravatar 测试
```
