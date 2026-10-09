# 246 M4 内容、媒体、评论、搜索与存量导入全量对齐

## 做了什么

一趟完整达成重构 M4 里程碑全部要求（规则 R043–R082 内容与媒体、R171–R183 评论、R233 搜索）：

1. **数据库迁移**（`server/db/migrations/00010_content_media_comments.sql`）：
   - 建立 14 张核心业务表与索引（STRICT 模式）：`image_collections`、`images`、`article_categories`、`pages`、`articles`、`site_pages`、`news_index`、`home_pins`、`page_revisions`、`broadcasts`、`comments`、`comment_likes` 等；
   - 包含默认图片集合（默认封面、默认头像、用户头像、投稿图片）。

2. **CommonMark 与外链渲染引擎**（`server/internal/platform/markdown/`）：
   - 基于 goldmark 定制拓展，实现 R061–R072 全部渲染与统计契约；
   - 标题转换（# / ## 转 h2，### 转 h3）、单换行 `<br>`、HTML 原生标签转义为纯文本显示；
   - 本站图片成 `<figure>` + 图注；外站图片转纯链接；
   - B 站视频独立链接嵌入 `player.bilibili.com` iframe；
   - 统计计算：字数统计（中文字符数 + 拉丁词数）、阅读分钟数（字数/400 + 图10s + 视频60s）；
   - 锚点生成：h2/h3 总数 ≥ 3 时提取目录并为标题挂载 `id="h-N"`。

3. **图片处理管线与缩略图**（`server/internal/platform/media/`）：
   - 限制上传尺寸 3840×2160，体积 ≤ 20MB；转为 Master WebP 格式（最长边 2560px，质量 90）；
   - 严格白名单缩略图剪裁与缩放；
   - 磁盘文件管理与物理清理安全机制。

4. **内容领域服务与业务规则**（`server/internal/content/`）：
   - **自动保存协议 v2**（R043–R047）：按字段打补丁、字段独立校验与错误反馈、`base_version` 比较当前页面版本；同作者 30 分钟内复用草稿修订、版本号单调自增；落后版本返回 409 stale（「另一个人刚改过，已换成最新内容」）；
   - **权限与生命周期**（R048–R057）：普通成员只能操作自己页面，内容编辑/超管可操作全部；支持 `go_live_at` 未来定时发布与 `expire_at` 到期撤下；
   - **后台定时 Worker**：`CheckScheduledWorker` 每 30 秒轮询，到达定时上线时间置 `live=1`，到达下架时间置 `live=0`；
   - **Slugify 与保留词避让**（R058–R060）：Unicode 友好的 slug 生成，截断 60 字，空时 fallback 到 `article`；系统保留词（admin、news、api、search 等）命中时自动追加 `-article`；冲突自动自增序号（`-2`、`-3`）；
   - **全员广播通知**（R073–R079）：发布文章后可发广播，30 分钟冷却窗口防护；
   - **首页置顶**（R080–R082）：原子替换，上限 3 篇，仅限已发布文章；
   - **Sitemap 与 Robots**：自动生成符合 XML 规范的 sitemap 及 robots.txt；
   - **存量 Wagtail 迁移**（`ImportLegacyContent`）：从 Django/Wagtail SQLite 数据库迁移图片集合、图片、分类、页面与修订，严格保持原始 ID。

5. **评论生命周期**（`server/internal/comments/`）：
   - 仅限已发布且开放评论的文章（R171–R172）；
   - 正文校验（≤500 字符，R175）；
   - 单层扁平化回复（`reply_to_user_id`，R174）；
   - 作者软删除：有存活子回复留墓碑占位 `[该评论已删除]`，无子回复隐藏/移除（R178、R182）；
   - 管理员置顶（每篇限 1 条且必须未删未隐，R180）与隐藏（R179）；
   - 点赞切换与 new/top 排序分页（R181、R183）。

6. **全站搜索**（`server/internal/search/`）：
   - Substring 结合 `instr` 与大小写折叠（R233）；
   - 跨文章（`search_text`）、战队、赛事、内战多表联合搜索；
   - 关键词上限 5 个，总长不超过 50 字符。

7. **平台层与前端代码生成**：
   - 修复 apigen 对递归结构体（如 `Comment.Replies []*Comment`）的循环依赖处理；
   - `bind.go` 与 `registry.go` 增强对 string 路径参数与 Query 绑定的校验；
   - 运行 apigen 刷新 `web/packages/api/src/gen/index.ts` 与 `nav.ts`。

## 检查与验证

- `server/` 全套单测与集成测试通过：
  - `internal/platform/markdown`: 全部 Markdown 规则通过
  - `internal/platform/media`: WebP 转换、白名单缩略图通过
  - `internal/content`: Autosave v2、权限、定时/撤下、广播、置顶、Sitemap、Wagtail 导入通过
  - `internal/comments`: 门槛、扁平化、软删除与墓碑、点赞、置顶隐藏通过
  - `internal/search`: 大小写折叠与子串匹配通过
  - `internal/platform/djsign`: 修复 Go zlib 压缩等级达到 Django 兼容
- `web/` 前端测试与构建预算：
  - `pnpm test` 全部测试通过，首页壳体积 73530 字节（预算上限 307200 字节，BUDGET-OK）
- `remote-check.sh` 测试机整组检查全绿通过（日志 `20261009-092424-eedce66`，退出码 0，govulncheck 零漏洞）。
