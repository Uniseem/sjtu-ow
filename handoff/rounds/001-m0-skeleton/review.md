# 001 复核结果

## 结论

需返工。整体质量好，但有 3 个问题会让生产环境直接失效。

## 验证记录

| 项目 | 结果 |
|---|---|
| ruff check / format | 通过 |
| pytest | 5 个测试通过 |
| `makemigrations --check` | 无遗漏迁移 |
| 生产配置 `check --deploy` | 0 issues |
| 开发服务器访问首页、`/healthz`、404、`/admin/` | 正常，CSP 头和后台放宽都生效 |
| `DEBUG=False` 下的自定义 404 | 生效 |
| 浏览器控制台 | 11 条 CSP 报错 |
| 生产配置跑 `render_error_pages` | 复现构建失败 |
| Caddyfile 语法 | 未验证（本机 Docker 未运行） |

## 必须修

- **A1** Docker 构建失败：`render_error_pages` 在 `collectstatic` 之前跑，生产用 manifest 存储，`{% static %}` 抛 `ValueError: Missing staticfiles manifest entry for 'css/app.css'`
- **A2** 全站内联 `style="` 被 CSP `style-src 'self'` 挡掉，字体变量全部不生效（28 处）
- **A3** htmx 注入的指示器样式同样被挡

## 建议修

- **B1** `/static/*` 一律 immutable 一年，但不带哈希的原始文件也在其中
- **B2** 健康检查用 `CREATE TEMP TABLE`，测不出真正的写失败，且与持久连接冲突
- **B3** 项目没有 git 仓库；编译产物 `static/css/app.css` 被提交
- **B4** CI 不构建镜像，抓不到 A1 这类构建期错误
- **B5** `X_FRAME_OPTIONS = "DENY"` 可能挡住 M2 的 Wagtail 页面预览

## 认可的判断

自定义用户模型的时机、SQLite PRAGMA 的测试方式（用文件型测试库）、Alpine CSP 构建、前台零第三方请求，这几处都处理得对。

## 文档更新

本轮无。
