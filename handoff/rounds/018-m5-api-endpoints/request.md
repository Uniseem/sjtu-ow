# 018 M5 第二部分：开放 API 的业务接口

> 用户外出期间，本轮仍由 Claude 实现 + 自查。

## 背景

017 做完了客户端、签名认证、限流和调用日志。本轮做业务接口。

设计依据：`docs/design.md` v1.5.7，11.4（通用参数）、11.5（数据对象）、11.6（通用资源接口）、11.7.1–11.7.4（场景接口）。

## 本轮范围

**做**：T1–T7。
**不做**：Webhook 投递与接口文档页面（019）。

## 任务

### T1 外键补齐

`Tournament.source_client`、`RegistrationStatusLog.actor_client` 两个指向 `ApiClient` 的外键（017 留的口子），以及 (source_client, external_id) 的部分唯一约束。

### T2 序列化与通用参数（设计 11.4、11.5）

- 赛事、报名、战队、名单成员、状态日志五种对象，字段严格按 11.5
- `include`：`tournament` / `team` / `members` / `members.ranks` / `logs`，受客户端配置限制
- `fields`：支持嵌套点号，`id` 总是返回，字段名写错返回 `400 invalid_field`
- `updated_since`、`limit`（默认 50、最大 200）、`cursor` 游标分页
- 列表统一按 `updated_at`、`id` 升序

### T3 赛事接口（11.6.1–11.6.3）

- `GET /api/v1/tournaments`（筛选 status、source、updated_since）
- `GET /api/v1/tournaments/{id}`（带 `description_html`）
- `PUT /api/v1/tournaments/external/{external_id}`：不存在创建（201）、存在更新（200）；`external_id` 只在当前客户端范围内唯一；有报名后改审核模式返回 `409 review_mode_locked`；`description_html` 只保留安全标签
- 本站草稿不通过 API 返回；上游自己推送的赛事任何状态都返回；`external_id` 只对推送它的客户端可见

### T4 报名接口（11.6.4–11.6.7）

- `GET /api/v1/registrations`（筛选 tournament、status、team、updated_since）
- `GET /api/v1/registrations/{id}`
- `GET /api/v1/registrations/{id}/logs`（升序、不分页）
- `POST /api/v1/registrations/{id}/review`：`action` + `roster_version` + `note`；名单版本对不上返回 `409 roster_version_mismatch`；驳回和撤销必填备注；只允许当前审核模式下上游能做的转换

### T5 场景接口（11.7.1–11.7.4）

- `GET /api/v1/tournaments/{id}/roster`（默认只看 approved，不分页）
- `GET /api/v1/tournaments/{id}/roster.csv`（带 BOM，列按设计）
- `GET /api/v1/tournaments/{id}/stats`
- `POST /api/v1/registrations/review-batch`（最多 100 条，逐条独立处理）

### T6 安全

- **联系方式任何情况下都不返回**
- 状态日志不返回具体操作人
- 上游只能看到自己推送赛事的 `external_id`

### T7 上游操作留痕

上游的审核写进状态日志时，`actor_type=upstream`、`actor_client` 指向该客户端。

## 测试要求

至少覆盖：五种对象的字段、`include` 权限、`fields`（含嵌套和错误字段）、游标分页与 `updated_since` 增量、草稿不可见、`external_id` 可见性、创建与更新赛事、`review_mode_locked`、名单版本不匹配、三种审核模式下上游能做和不能做的操作、批量审核部分失败、roster / CSV / stats 的内容、联系方式不出现在任何响应里、日志里不出现管理员身份。

## 验收标准

1. `ruff` / `pytest` / `makemigrations --check` / 生产 `check --deploy`
2. 用真实签名把全部接口打一遍，贴出关键响应
3. 贴出 CSV 前几行
4. 贴出一次 `roster_version_mismatch` 和一次批量审核部分失败的响应
5. 回归 + `docker build` + `caddy validate`
6. git 提交，信息以 `018:` 开头

## 输出要求

- `handoff/rounds/018-m5-api-endpoints/report.md`，自查后写 `review.md`，更新 `handoff/STATUS.md`
