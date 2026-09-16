# 002 修复 001 复核发现的问题

> 回填记录，完整提示词当时在对话里给出。

## 本轮范围

只修 001 复核列出的问题，不顺手重构，不新增依赖。

## 任务

- A1 Docker 构建失败：错误页改为自包含，产物管理方式二选一并说明
- A2 内联 style：字体规则进 `input.css`，模板改用类名，**禁止**加 `unsafe-inline`
- A3 htmx：`includeIndicatorStyles = false`，指示器样式写进 CSS
- B1 静态文件缓存按是否带哈希区分
- B2 健康检查改为对真实数据做写入验证
- B3 `git init` 并提交 M0；`static/css/app.css` 加入 gitignore
- B4 CI 增加镜像构建
- B5 只验证 Wagtail 预览的 `X-Frame-Options` 行为并给方案，不改代码
- C1–C3 可选：非 root 用户、邮件丢弃时打日志、后台路径前缀改为可配置

## 验收标准

docker build 成功、首页 0 条 CSP 报错、templates 无 `style="`、错误页不引用外部资源、ruff、pytest、`makemigrations --check`、`check --deploy`、`caddy validate`、git log。
