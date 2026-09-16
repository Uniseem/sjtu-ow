# 002 实现报告

> 回填摘要。

## 结论

A1、A2、A3、B1、B3、B4 已修；B2 按要求改为真实写入探活；B5 只验证不改代码；C2、C3 做了，C1 说明理由后未做。

## 逐条结果（摘要）

- A1：错误页改为自包含（内联 `<style>`，不继承 `base.html`），产物提交仓库，Dockerfile 去掉生成步骤，CI 增加漂移检查
- A2：字体规则进 `assets/css/input.css`，模板改用 `.font-nav` / `.font-button` / `.font-numeric` / `.font-code`，CSP 未改
- A3：`htmx.config.includeIndicatorStyles = false`，`.htmx-indicator` 样式写进 CSS
- B1：带 12 位哈希的静态文件 immutable 一年，其余 300 秒
- B2：改为对 `django_content_type` 写入后回滚
- B3：`git init -b main`，首提交 `9bc97f2`
- B4：CI 增加 `docker build` 和错误页 `git diff --exit-code`
- B5：Wagtail 8 的 `PreviewOnEdit`、`StreamFieldBlockPreview` 会覆盖 `X-Frame-Options`；`PreviewRevision`、`ViewDraftView` 不会
- C1 未做：镜像改非 root 后命名卷属主会导致写失败，留到以后和卷初始化一起处理

## 设计偏差（交给 Claude 改文档）

1. 13.15 节「构建镜像时生成错误页」→ 改为产物提交仓库、CI 校验漂移
2. 错误页与 `base.html` 和站点样式表解耦
3. `/static/*` 不再一律一年 immutable

## 不同意 / 未修

- 错误页自包含后，Django 渲染的错误页内联 `<style>` 会被 CSP 挡住、页面无样式；因为不允许加 `unsafe-inline`，本轮不处理
