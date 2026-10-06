# 211 失效 b23 短链缓存与正文字段存算（D1）

## 背景

210 全站复核（`handoff/rounds/210-full-review/review.md`）找到唯一一条高严重度问题：

- **D1**：`video_src` 的 b23 分支走 Wagtail `get_embed`，Wagtail 只在查到结果时才写 `Embed` 缓存行；查不到（链接过期、b23 不通）什么都不记，于是**正文每渲染一次就联网一次**（`follow_b23` 是 `urlopen(timeout=10)`）。渲染次数还被放大：一次文章页请求渲染 3 遍（`render` + `facts` 里 `analyse`、`plain_text`），每张文章卡再渲染 2 遍，**每次搜索把所有已发布文章正文和赛事内战说明渲染一遍**。任何验证过邮箱的成员发一篇带几十条失效 b23 链接的文章，就能让每次搜索等几百秒、worker 卡住。
- **D10**（与 D1 叠加）：字数和阅读时间每次都重新解析 Markdown。

210 的修法顺序把 D1 定为第 0 步、先修；复核给了修法方向：失败也记一条（`Embed` 有 `cache_until`），字数、阅读时间发布时算好存进字段，搜索不再逐篇渲染。

`STATUS.md` 原计划的「211 自动保存收尾」顺延为 212（依次类推），见 STATUS.md。

## 本轮范围

做：

1. b23 短链**查询失败也缓存**：`get_embed` 抛 `EmbedException` 时写一条 `Embed` 行（空 html，`cache_until` 一小时后），到期自动重试；查到过结果的照旧永久缓存
2. 顺手修同函数的 **F10/D4**：`?bvid=` 查询参数过 `BV_RE` 校验，非法的当成没有（现在能往播放器地址里塞 `autoplay=1` 这类参数）
3. `ArticlePage` 增加保存时算好的字段：`body_plain`（正文纯文本）、`body_words`（字数）、`body_minutes`（阅读分钟数）；文章页头和文章卡改读字段，删掉每次请求重新解析的 `facts` 属性
4. `Tournament`、`Scrim` 增加 `description_plain`；站内搜索的文章和赛事/内战两类改匹配存好的文本，不再每次搜索逐篇渲染；内战邮件说明也读存好的文本
5. 数据迁移：回填已有的文章、赛事、内战
6. 设计文档同步（5.2、12.5.1、12.8.1、12.9.1、13.16、细节 6.3、附录 D）

明确不做：

- 210 复核的其它条目（T1、A1、S1……按顺序在 212 及以后）
- 搜索匹配规则、字数算法本身不变（用户可见行为不变）
- 不引入新的缓存表、不改动 Wagtail 的 `Embed` 模型
- 文章页身的渲染仍是一次现场渲染（预渲染页本来就是静态的）；不把渲染好的 HTML 存库

## 任务

1. `content/embeds.py`：加 `remember_failed_lookup(url)`（写 `Embed` 行，`cache_until` 一小时）和 `?bvid=` 的 `BV_RE.fullmatch` 校验
   - 验证：`content/tests/test_markdown.py` 新测试：mock `follow_b23` 抛 `EmbedNotFoundException`，渲染两次只联网一次；把缓存行的 `cache_until` 改到过去后再渲染会重试
2. `content/markdown.py`：`video_src` 的 b23 分支在 `EmbedException` 时记失败再返回 `""`
   - 验证：同上；原有 `test_a_short_link_is_looked_up_once`（成功缓存）仍绿
3. `content/models.py`、`tournaments/models.py`、`scrims/models.py`：新字段 + `save()` 里重算（`update_fields` 不含源字段时不动；含源字段时把派生字段一起带上）；`content/article_meta.py` 加一个一次渲染同时算出纯文本、字数、分钟数的函数
   - 验证：新测试：发布后字段值等于 `article_meta.facts` 算出来的；再发布新正文后字段跟着变；`update_fields=["status"]` 保存不碰派生字段
4. 模板（`article_page.html`、`post_card.html`）改读字段；删 `ArticlePage.facts` 属性
   - 验证：新测试：把 `article_meta.facts` 换成必炸的桩，文章页、资讯列表照样 200 且分钟数、字数正确
5. `search/services.py`：`search_articles` 用 `page.body_plain`，`search_events` 用 `row.description_plain`；`scrims/notifications.py` 的信用 `scrim.description_plain`
   - 验证：新测试：把 `content.markdown.plain_text` 换成必炸的桩，搜索照样命中；原有 `test_search_matches_the_words_not_the_markup` 等搜索测试全绿
6. 迁移：`makemigrations` + 数据迁移回填；`makemigrations --check --dry-run` 干净
7. 每条新规则做变异验证（把检查改坏，确认对应测试变红，再改回来）

## 验收标准

- `uv run ruff check . && uv run ruff format --check .`
- `uv run python manage.py tailwind build`（模板改了类名的话 `--force`）
- `uv run pytest -q` 全绿（含新增测试）
- `uv run python manage.py makemigrations --check --dry-run`
- 生产配置 `check --deploy`（AGENTS.md 那组环境变量）
- 上面全部在测试机上跑：`bash scripts/remote-check.sh`
