# 017 M5 第一部分：API 客户端、签名认证与调用日志

> 用户外出期间，本轮仍由 Claude 实现 + 自查。

## 背景

M4 已完成。M5「开放 API 与 Webhook」拆成三轮：**017 客户端与签名认证（本轮）**、018 读写接口、019 Webhook 与接口文档。

设计依据：`docs/design.md` v1.5.7，重点读 11.1、11.2、11.3、11.5、11.7.5、12.10.1、12.10.2。

## 本轮范围

**做**：T1–T6。
**不做**：业务接口（018）、Webhook（019）。本轮只做 `GET /api/v1/ping`，用来验证签名链路。

依赖：按设计 2.2 引入 `djangorestframework` 和 `drf-spectacular`（设计里已经写明用它们）。

## 任务

### T1 数据表（设计 12.10.1、12.10.2）

`ApiClient`（名称、Key ID、加密的 Secret、授权范围、允许的展开项、限流、Webhook 相关字段、启用、最近使用、吊销时间）和 `ApiRequestLog`（客户端、请求 ID、方法、路径、状态码、错误码、IP、耗时），**不记录请求体和响应体**。

### T2 签名认证（设计 11.2）

按 11.2.3 的七步顺序实现，错误码严格对应：`missing_auth` / `invalid_api_key` / `timestamp_expired` / `nonce_reused` / `invalid_signature` / `scope_denied` / `rate_limited`。签名算法按 11.2.2：方法、路径、规范化查询字符串、时间戳、Nonce、请求体 SHA-256，HMAC-SHA256 十六进制小写，**常数时间比较**。

### T3 Nonce 与限流

Nonce 10 分钟内不可重复；限流按客户端的 `rate_limit_per_minute`（默认 600）。两者都用现有的数据库缓存。

### T4 统一响应与日志

- 单对象 `{"data": {...}}`、列表 `{"data": [...], "next_cursor": ..., "has_more": ...}`、错误 `{"error": {"code", "message", "details"}}`
- 每个响应带 `X-Request-Id`
- 每次调用写一条 `ApiRequestLog`（含认证失败的情况）

### T5 连通性接口（设计 11.7.5）

`GET /api/v1/ping` 返回客户端名称、授权范围、允许的展开项、服务器时间。任何有效客户端都能调用。

### T6 后台管理

「设置 → API 客户端」（超级管理员）：创建（**Secret 只显示一次**）、重新生成密钥（旧的立即失效）、启用 / 停用、吊销、查看最近调用日志。

## 测试要求

至少覆盖：七步校验逐条的错误码、签名算法与设计给的 Python 示例一致、查询字符串规范化（排序、编码）、请求体摘要、Nonce 重放、限流、授权范围不足、`ping` 的返回内容、日志写入（含失败）、Secret 只显示一次、重新生成后旧密钥失效、吊销后拒绝。

## 验收标准

1. `ruff` / `pytest` / `makemigrations --check` / 生产 `check --deploy`
2. 用设计 11.2.2 里给出的**那段 Python 示例代码**（原样照抄）签一个请求，真实打到 `/api/v1/ping`，贴出请求头和响应
3. 贴出七种错误的真实响应
4. 后台创建客户端的截图或文字输出（含「只显示一次」的提示）
5. 回归：前台各页、`/healthz`、后台
6. `docker build`、`caddy validate`
7. git 提交，信息以 `017:` 开头

## 输出要求

- `handoff/rounds/017-m5-api-auth/report.md`，自查后写 `review.md`，更新 `handoff/STATUS.md`
