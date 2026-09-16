# 002 复核结果

## 结论

需返工。A1、A2、A3 确认修好；但 B2 的修法引入了比原问题更严重的新问题，另外错误页失去了样式。

## 验证记录

| 项目 | 结果 |
|---|---|
| A1 | 生产配置下 `render_error_pages` 已能正常输出；`sjtu-ow:ci` 镜像存在（991MB），构建确实跑过 |
| A2 | `templates/` 下 0 处 `style="`；首页控制台 0 条报错；截图确认样式正常 |
| A3 | 首页没有任何 `<style>` 元素 |
| B1 | 哈希文件 immutable 一年、其余 300 秒；12 位哈希正则与 Django/WhiteNoise 默认一致 |
| B3 | 1 个提交、121 个文件，工作区干净，`static/css/app.css` 未被跟踪 |
| B4 | CI 增加了镜像构建和错误页漂移检查；本地重新生成错误页无漂移 |
| ruff / pytest / makemigrations / check --deploy | 全部通过，8 个测试，0 issues |
| B5 | 核对 Wagtail 源码：`generic/preview.py:122`、`:184` 有 `xframe_options_sameorigin_override`；`PreviewRevision`、`ViewDraftView` 没有，结论属实 |

## 必须修（进入 003）

- **R1** 健康检查在数据库「忙」时误报故障。实测：另一个连接占住写锁时 `/healthz` 等待 5.2 秒后返回 503，detail 为 `database is locked`；释放后 0.01 秒返回 200。影响：探活要抢全库写锁、误报站点故障、每次占住一个 Web 进程 5 秒
- **R2** Django 渲染的 404 / 403 / 429 / 500 页面完全没有样式。实测 404 页面报 1 条 CSP 错误、显示为浏览器默认样式

## 认可的判断

- B5 的分析准确，我核对过源码行号
- C1 不做的理由成立：镜像改非 root 后命名卷属主确实会导致 `collectstatic` 和 SQLite 写失败
- 不给 CSP 加 `unsafe-inline` 的坚持是对的

## 文档更新

`docs/design.md` 升到 v1.5.2：

1. 13.15 节：错误页改为「Django 渲染的引用独立 `error.css`、维护页完全自包含」，产物提交仓库并由 CI 校验漂移
2. 13.10 节：静态文件缓存按是否带哈希区分
3. 16.6 节：健康检查必须区分数据库「忙」和「坏」，并限制探活等待时间
4. 附录 C 增加两条默认参数
