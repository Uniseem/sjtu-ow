# 001 M0 项目骨架

> 回填记录。这一轮的要求当时是直接在对话里给的，这里保留摘要，方便以后追溯。

## 背景

项目从零开始，先搭骨架，不实现业务功能。

## 本轮范围

只做 `docs/design.md` 第 18 章的 M0，不实现账号、战队、赛事、内战、投稿、开放 API、AI 审核。

## 任务（13 项）

1. 项目骨架和目录结构（设计 2.4 节）
2. settings 拆分 base / dev / prod，环境变量按 16.3 节
3. 自定义用户模型 `accounts.User`，必须在第一次迁移之前建好（12.3.1 节）
4. 九个应用的空骨架，每个含 models / services / views / tests
5. 全站布局和组件模板，只用 daisyUI 语义颜色，字体只通过 CSS 变量（13.2、13.3 节）
6. htmx、Alpine（CSP 构建）、SortableJS 自托管，不走 CDN，不加载网络字体
7. 首页占位页，以及 404 / 403 / 429 / 500 / 维护页，不依赖数据库（13.15 节）
8. `/healthz`：M0 实现数据库和磁盘检查，worker 心跳和任务积压留接口（16.6 节）
9. Dockerfile、docker-compose、Caddyfile，按 13.13.2 节分流，配好维护页
10. 数据库缓存表接入部署流程；`init_site` 先给空壳
11. CI：ruff、pytest、`makemigrations --check`、`check --deploy`
12. README：本地启动、测试环境与生产的区别（16.10 节）
13. 测试覆盖健康检查、首页、自定义用户模型、SQLite PRAGMA

## 硬性约束

技术栈按设计 2.2 节，不换组件；不新增依赖；界面中文、命名英文；业务逻辑放 `services.py`；不写 TODO 占位冒充实现；不自行改设计文档。
