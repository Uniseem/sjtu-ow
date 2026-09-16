# 017 实现报告

> 用户外出期间由 Claude 实现 + 自查。M5 第一部分。

## 结论

T1–T6 已完成：API 客户端表和调用日志表、七步签名校验、Nonce 与限流、统一响应格式、`GET /api/v1/ping`、后台客户端管理（Secret 只显示一次）。345 个测试通过（本轮新增 20 个）。用**设计里给出的那段 Python 示例代码原样**签名，真实打通了 `/api/v1/ping`。

按设计 2.2 引入 `djangorestframework` 和 `drf-spectacular`（设计的技术栈表里就写着这两个）。

## 逐条结果

### T1 数据表

`ApiClient` 按设计 12.10.1（含 Webhook 的四个字段，019 才用），**Secret 用 `EncryptedTextField` 加密存储**——验签需要原文，所以不能只存哈希。`ApiRequestLog` 按 12.10.2，**不记录请求体和响应体**。

### T2 签名认证

`integrations/signing.py` 按 11.2.2 实现待签名字符串和 HMAC；`integrations/api.py` 的 `authenticate()` 严格按 11.2.3 的七步顺序，错误码一一对应。签名比较用 `hmac.compare_digest`（常数时间）。查询字符串按「解码后排序、RFC 3986 编码」规范化，重复参数也会按值排序。

### T3 Nonce 与限流

Nonce 用数据库缓存的 `add()` 做一次性写入，TTL 10 分钟；限流复用 010 的 `core.ratelimit`，按客户端的 `rate_limit_per_minute`（默认 600）。

### T4 统一响应与日志

`data_response` / `list_response` / `error_response` 三个辅助函数产出设计 11.1 的三种格式；DRF 的异常处理器统一改写成 `{"error": {...}}`。`ApiRequestLogMiddleware` 给每次 `/api/` 调用写一条日志，**认证失败也记**（客户端为空）。响应头的 `X-Request-Id` 由 M0 就有的中间件提供。

### T5 连通性接口

`GET /api/v1/ping` 返回客户端名称、授权范围、允许的展开项和服务器时间（ISO 8601、UTC、带 Z）。任何有效客户端都能调，不需要特定范围。

### T6 后台管理

「设置 → API 客户端」（超级管理员）：列表、新建（勾选范围和展开项、设限流）、详情（重新生成密钥 / 停用启用 / 吊销 / 最近 50 条调用日志）。**Secret 只在创建和重新生成之后的那一次页面渲染里显示**，存在会话里用完即删。

## 验收输出

### 1. 检查与测试

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
224 files already formatted

$ uv run python -m pytest -q
345 passed in 22.03s

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

> drf-spectacular 一开始会扫描 Wagtail 自带的后台 API 并报 9 条警告，让 `check --deploy` 不再干净。已经加了预处理钩子，只保留 `/api/v1/` 的接口，警告消失。

新增 20 个测试：正确签名、七种错误码、签名覆盖查询字符串和请求体、Nonce 重放、限流、重新生成后旧密钥失效、吊销、规范化查询字符串、待签名字符串与设计一致、展开项权限、授权范围不足、调用日志（成功与失败）、`last_used_at`、后台权限、Secret 只显示一次、**Secret 在数据库里是密文**。

### 2. 用设计里的示例代码真实调用

`sign_request()` 从设计 11.2.2 原样复制，没有改一个字符：

```
请求头: {
  "X-Api-Key": "ak_a9933fe4db52",
  "X-Timestamp": "1789561991",
  "X-Nonce": "a9c3b41d028723ff2618f1af5148c499",
  "X-Signature": "ab530cd8f538a66e9e27aedd6b52d93030e919a25a5d30498aab4c0fc710af03"
}

响应: 200
{
  "data": {
    "client": "验收上游",
    "scopes": ["tournaments:read", "registrations:read", "registrations:review"],
    "allowed_includes": ["team", "members"],
    "server_time": "2026-09-16T12:33:11Z"
  }
}
X-Request-ID: qeriCcbxOjdP
```

### 3. 七种错误

```
1 missing_auth      : missing_auth
2 invalid_api_key   : invalid_api_key
3 timestamp_expired : timestamp_expired
4 nonce_reused      : nonce_reused
5 invalid_signature : invalid_signature
6 scope_denied      : 单元测试覆盖（ping 不要求范围，带范围的接口在 018）
7 rate_limited      : rate_limited
```

调用日志（含失败）：

```
GET /api/v1/ping → 429 rate_limited 1ms
GET /api/v1/ping → 200  1ms
GET /api/v1/ping → 200  3ms
认证失败（无客户端）的日志: 5 条
```

### 4. 后台

```
创建后页面含「只显示这一次」: True
显示的 Secret 片段: uCUJdOWmkP…
再次打开列表还显示吗: False
详情页说明 Secret 不再展示: True
吊销后: 已吊销 | 可用: False
```

### 5. 回归

```
/            200    /news/         200    /teams/   200
/lfg/        200    /tournaments/  200    /healthz  200
```

### 6. docker / caddy

```
Successfully built 45ddfe4c4671
Valid configuration
```

### 7. 清理

验收用的两个客户端、调用日志和账号都已删除。

## 设计偏差

**没有改设计文档。** 实现按 11.1–11.3、11.7.5、12.10 做。三点说明：

1. **Nonce 按客户端分桶**（缓存键里带客户端 ID）。设计只说「这个 Nonce 在 10 分钟内没有出现过」，按客户端分桶更合理：两个上游各自生成的随机串撞车不应该互相影响。
2. **Nonce 长度校验**（16–64）不通过时返回 `invalid_signature`。设计的请求头表里写了长度要求，但七步校验里没有对应的错误码，归到签名不合法最接近。
3. **drf-spectacular 只扫 `/api/v1/`**：否则 Wagtail 自带的后台 API 会污染文档和 `check --deploy`。

## 未完成 / 不同意

1. **业务接口**（赛事、报名、名单、统计、审核、CSV）是 018。
2. **Webhook 投递**和**接口文档页面**是 019。
3. **调用日志 90 天清理**、**Webhook 记录 180 天清理**要接到设计 16.5 的每日清理任务里，放在 019。
4. `RegistrationStatusLog.actor_client` 和赛事的 `source_client` 两个外键等 018 用到时再加迁移。

## 顺带发现

1. DRF 的 `Request` 是包装对象，在视图里 `request.api_client = ...` 不会出现在中间件看到的 `HttpRequest` 上，要同时写到 `request._request`。
2. `request.GET.items(multi=True)` 不存在（那是 Werkzeug 的写法），Django 要用 `getlist()` 自己展开。
3. `django.utils.timezone.utc` 在新版本里已经没了，用 `datetime.timezone.utc`。

## 需要确认

无。

## 改动文件

新增：`integrations/models.py`、`signing.py`、`api.py`、`views.py`、`urls.py`、`services.py`、`middleware.py`、`schema.py`、`wagtail_hooks.py`、`templates/integrations/{index,create,detail}.html`、`migrations/0001_initial.py`、`tests/test_api_auth.py`。

修改：`sjtu_ow/settings/base.py`（DRF、spectacular、中间件、签名参数）、`sjtu_ow/urls.py`、`pyproject.toml`、`uv.lock`、`README.md`、`handoff/STATUS.md`。
