# 上海交通大学守望先锋社区网站

Django + Wagtail 站点。设计依据见 [`docs/design.md`](docs/design.md)（v1.5.1）。当前里程碑是 **M0 项目骨架**，不含账号、战队、赛事等业务功能。

## 技术栈

- Python 3.13，依赖用 [uv](https://docs.astral.sh/uv/) 管理
- Django 6.0、Wagtail 8.0、SQLite（WAL）
- 前台：Django 模板 + HTMX + Alpine.js（CSP 构建）+ Tailwind CSS v4 + daisyUI
- 样式由 `django-tailwind-cli` 编译，不安装 Node。源文件在 `assets/css/input.css`（不能放进 `STATICFILES_DIRS`，否则 WhiteNoise 哈希存储会处理 `@import "tailwindcss"` 并失败），编译结果在 `static/css/app.css`。
- 静态资源：WhiteNoise 存储后端（内容哈希 + 预压缩）；生产由 Caddy 直接提供
- 异步任务：Django Tasks + `django-tasks-db`
- 代码检查：ruff；测试：pytest + pytest-django

### 自托管前端脚本（不走 CDN）

| 文件 | 版本 | 来源 |
|---|---|---|
| `static/vendor/htmx.min.js` | 2.0.10 | [htmx v2.0.10](https://github.com/bigskysoftware/htmx/releases/tag/v2.0.10) |
| `static/vendor/alpine.csp.min.js` | 3.17.1 | npm `@alpinejs/csp` |
| `static/vendor/Sortable.min.js` | 1.15.6 | [SortableJS 1.15.6](https://github.com/SortableJS/Sortable/releases/tag/1.15.6) |

不加载 Google Fonts 或其他网络字体。

## 本地开发

需要 Python 3.13 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)。

```bash
cd sjtu-ow
uv sync
uv run python manage.py migrate
uv run python manage.py createcachetable
uv run python manage.py createsuperuser
uv run python manage.py tailwind runserver
```

`tailwind runserver` 会编译 `static/css/app.css`（已 gitignore，不要提交）。只编译、不启动服务器可以用 `uv run python manage.py tailwind build`。首次 `tailwind` 命令会下载 Tailwind CLI Extra 二进制到 `.django_tailwind_cli/`（已 gitignore）。另开一个终端运行 worker（M0 还没有实际任务）：

```bash
uv run python manage.py db_worker
```

开发配置是 `sjtu_ow.settings.dev`：邮件打到控制台，默认关闭预渲染，缓存用内存。

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

提交前可以用 pre-commit（可选）：

```bash
uvx pre-commit install
```

## 环境区别（设计文档 16.10 节）

| 环境 | 说明 |
|---|---|
| 本地开发 | `sjtu_ow.settings.dev`。邮件输出到控制台。`PRERENDER_ENABLED` 默认 `false`，页面由 Django 实时渲染。 |
| 测试环境 | 与生产部署在同一台服务器上的另一套 Docker Compose 项目（例如 `-p sjtu-ow-test`），独立子域名、数据卷和数据库。配置 `EMAIL_ALLOWLIST`，只给名单里的邮箱发信。页面应显示「测试环境」横幅、`robots.txt` 禁止抓取（横幅和 robots 在后续里程碑落地）。 |
| 生产环境 | `sjtu_ow.settings.prod`。`PRERENDER_ENABLED=true`。静态资源收集到持久化 `static` 卷（只新增、不删除旧文件）。SMTP 在后台配置（M1），不放环境变量。 |

复制 [`.env.example`](.env.example) 为 `.env` 后再启动 Compose。`DJANGO_SECRET_KEY` 和 `FIELD_ENCRYPTION_KEY` 必须单独备份。

## 生产 / 测试环境启动

先执行迁移（不要指望容器自动 migrate，升级流程见设计 16.8 节）：

```bash
cp .env.example .env
# 编辑密钥、域名、CADDY_SITE_ADDRESS
docker compose -f deploy/docker-compose.yml build
docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml exec web python manage.py migrate
docker compose -f deploy/docker-compose.yml exec web python manage.py createcachetable
docker compose -f deploy/docker-compose.yml exec web python manage.py createsuperuser
```

`web` 启动脚本会执行 `createcachetable` 和 `collectstatic --noinput`（没有 `--clear`，旧的带哈希文件会留在卷上）。

测试环境用独立项目名，避免和正式站抢数据卷：

```bash
docker compose -p sjtu-ow-test -f deploy/docker-compose.yml --env-file .env.test up -d
```

停掉 `web` 后，Caddy 对会打到后端的请求返回维护页；已经生成的预渲染公开页面仍可访问。

初始化命令目前只打印计划内容，不写数据：

```bash
uv run python manage.py init_site
```

## 健康检查

`GET /healthz` 在数据库可读写且数据盘剩余空间大于 20% 时返回 200，否则 503。worker 心跳和任务积压接口已留在 `core/health.py`，M1 再计入状态。

## CI

使用 **GitHub Actions**（[`.github/workflows/ci.yml`](.github/workflows/ci.yml)）：ruff、pytest、`makemigrations --check`、生产配置下的 `check --deploy`、重新生成错误页后 `git diff` 必须为空、`docker build`。

错误页是自包含 HTML，提交在 `deploy/error_pages/`。改 `templates/errors/` 后运行：

```bash
uv run python manage.py render_error_pages
```
