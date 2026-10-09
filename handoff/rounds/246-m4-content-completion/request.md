# 246 M4 内容、媒体、评论、搜索与存量导入全量对齐

## 背景

M4 内容里程碑终局轮次。在用户「把 M4 也给我一次性做完」的明确指示下，本轮将 M4 所涉的全部业务规则（R043–R082 内容与媒体、R171–R183 评论、R233 搜索）及存量 Wagtail 数据导入一次性完整交付，完成整个 M4 里程碑。

依据 `docs/rewrite-research/12-architecture.md` 5.5（自动保存 v2）、5.12（图片管线）、5.13（Markdown 渲染与外链解析）、5.14（搜索）、7（存量导入）、8.1、11.2 以及 `docs/rewrite-research/05-business-rules.md`：

1. **自动保存协议 v2 与版本控制**（规则 R043–R047）：
   - `POST /api/articles`：用初始合法字段建草稿，返回 `{id, location, version}`；
   - `PATCH /api/articles/{id}`：按字段打补丁（合法的存、不合法的留旧值并报错），`base_version` 比较当前页面版本，冲突返回 409 stale（「另一个人刚改过，已换成最新内容」）；
   - 30 分钟内同作者保存复用草稿修订，超过 30 分钟新增修订，版本号单调自增。
2. **发布门槛与定时控制**（规则 R048–R057）：
   - 普通成员仅能发布/撤下自己的文章；内容编辑与超管可操作任何文章；纯投稿者受限；
   - 支持 `go_live_at` 定时上线与 `expire_at` 到期撤下；
   - 后台 Worker 巡查（每 30 秒）：到达上线时间自动置 `live=1`，到达下架时间自动置 `live=0`。
3. **网址片段与保留词**（规则 R058–R060）：
   - 支持 Unicode 友好的 Slugify，截断 60 字，取不到回退 `article`；
   - 命中系统保留词（admin、news、api、auth、search 等）自动追加 `-article`；
   - 冲突自动递增 `-2`、`-3`。
4. **Markdown 渲染与外链对拍**（规则 R061–R072）：
   - CommonMark + GFM 表格 + 删除线；换行即 `<br>`；原生 HTML 转义为文本；
   - 标题降级：`#`/`##` 映射为 `<h2>`，`###` 及以下为 `<h3>`；
   - 本站图片成 `<figure>` 与图注；外站图片转纯链接；
   - 裸 URL 自动链接；出处脚注语法；B 站独立视频链接嵌入 iframe；
   - 字数统计（中文字符+拉丁词数）与阅读时长计算；3 个以上 h2/h3 标题提取目录与锚点。
5. **图片管线与缩略图**（12 号文档 5.12）：
   - 上传图片尺寸上限 3840×2160，体积上限 20MB；转为 Master WebP 格式（最大 2560px，质量 90）；
   - 严格白名单缩略图渲染，非白名单拒绝；
   - 存在性校验与磁盘文件管理。
6. **评论生命周期与安全**（规则 R171–R183）：
   - 仅限已发布且开放评论的文章；
   - 最大 500 字符；单层扁平化回复（`reply_to_user_id`）；
   - 作者软删除（有子回复留墓碑 `[该评论已删除]`，无子回复移除）；
   - 管理员置顶（每篇限 1 条且必须未删未隐）与隐藏；
   - 点赞切换与 new/top 排序。
7. **全站搜索**（规则 R233）：
   - Substring 结合 `instr` 与大小写折叠；
   - 跨文章（`search_text`）、战队、赛事、内战搜索；
   - 关键词上限 5 个，总长不超过 50 字符。
8. **存量 Wagtail 迁移与站点元数据**（12 号文档 7、8.1）：
   - 存量图片库、分类、Wagtail 页面与修订无损导入，保留主键 ID；
   - Sitemap 与 Robots.txt 自动生成。

## 本轮范围

### 做什么

1. **数据库迁移**（`server/db/migrations/00010_content_media_comments.sql`）：
   - 创建 `image_collections`、`images`；
   - 创建 `article_categories`、`pages`、`articles`、`site_pages`、`news_index`、`home_pins`、`page_revisions`、`broadcasts`；
   - 创建 `comments`、`comment_likes`。
2. **Markdown 渲染引擎**（`server/internal/platform/markdown/`）：
   - 基于 goldmark 实现符合 R061–R072 要求的完整渲染管线，含图片/视频/锚点目录处理。
3. **媒体处理库与路由**（`server/internal/platform/media/`）：
   - 图片处理（解码、尺寸缩放、WebP 转换、缩略图按白名单剪裁）。
4. **内容领域服务**（`server/internal/content/`）：
   - `model.go`、`store.go`、`slug.go`、`service.go`、`api.go`、`sitemap.go`、`import.go`。
5. **评论领域服务**（`server/internal/comments/`）：
   - `model.go`、`store.go`、`service.go`、`api.go`。
6. **搜索领域服务**（`server/internal/search/`）：
   - `service.go`、`api.go`。
7. **平台层与前端代码生成**：
   - 修复 apigen 对递归结构体的处理；
   - `bind.go` 与 `registry.go` 支持 string 路径参数与 Query 绑定校验；
   - 运行 apigen 刷新 `web/packages/api/src/gen/index.ts` 与 `nav.ts`。
8. **测试套件**：
   - `server/internal/platform/markdown/markdown_test.go`
   - `server/internal/platform/media/media_test.go`
   - `server/internal/content/m4_full_test.go`
   - `server/internal/comments/service_test.go`
   - `server/internal/search/service_test.go`

### 不做什么

- 不动现行正式站（169.58.217.180）。
- M5 战队域留待下一里程碑。
