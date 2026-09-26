# 083 实现报告

## 结论

完成。资讯列表、文章页、搜索、普通页面、投稿页按 v3.0 调了版式。

## 逐条结果

1. **资讯列表**：`components/post_card.html`（新）代替 `article_row.html`（删除）：封面，没有封面用 `components/category_wash.html`（新）——按分类换色调的渐变加分类图标（公告资讯、赛事通知奖杯、攻略地图、战报旗子、心得笔）；分类、日期、标题、两行摘要、作者首字头像。桌面三列、平板两列、手机一列，`data-reveal` 依次出现。投稿按钮改色调按钮，去掉 NEWS 眉标
2. **筛选标签**：选中项前面有对勾（样式里用蒙版画，所有 `c-tabs` 都有，不用改模板）
3. **文章页**：分类改为可点的色调标签；标题字号随屏宽；元信息行作者首字头像 + 昵称 + 日期；封面 28px 圆角；文末 `c-byline`（大头像、作者、栏目、发布）代替 `c-facts`；右栏 `c-related` 圆角卡，桌面上停在顶栏下面；去掉 `border-b-2 border-fg`
4. **搜索**：`c-searchbar` 填充式胶囊搜索栏（图标、输入框、主要按钮），聚焦时白底主色边；每类结果放在 `c-news` 圆角卡里，标题旁 `c-count` 数量徽标；去掉 SEARCH 眉标和横线
5. **普通页面**：侧栏标题「关于本站」（去掉 ABOUT）；「最后更新」和日期包在一起，不再被 flex 间距拆开
6. **投稿页**：去掉 SUBMIT 眉标
7. **设计**：13.2.7 加 `c-post`、`c-byline`、`c-related`、`c-searchbar`、`c-count`；13.2.8「刊物列表」骨架改为卡片网格；13.2.3 的「无边框搜索栏」例外扩到搜索页

## 验收输出

```
== ruff
All checks passed!
246 files already formatted
== tailwind
Built production stylesheet 'C:\Users\fyc12\Desktop\Claudee\sjtu-ow\static\css\app.css'.
== pytest
978 passed in 237.28s (0:03:57)
== makemigrations
No changes detected
== check --deploy
System check identified no issues (0 silenced).
```

变异（`handoff/rounds/083-editorial-pages/mutate.py`）：

```
KILLED   没封面的卡片用回同一种渐变  | 1 failed in 2.10s
KILLED   占位里没有分类图标  | 1 failed in 3.59s
KILLED   有封面的卡片也盖上占位  | 1 failed in 3.62s
KILLED   资讯列表用回一行一篇  | 1 failed in 3.41s
KILLED   选中的筛选标签没有对勾  | 1 failed, 1 passed in 3.96s
KILLED   文章元信息没有作者头像  | 1 failed, 2 passed in 4.46s
KILLED   文末用回资料表  | 1 failed, 2 passed in 4.40s
KILLED   同栏目最新用回粗线  | 1 failed, 2 passed in 4.59s
KILLED   搜索框用回深色边框  | 1 failed, 3 passed in 4.94s
KILLED   搜索结果组没有数量徽标  | 1 failed, 3 passed in 5.22s
KILLED   资讯页又带英文眉标  | 1 failed, 4 passed in 5.52s
KILLED   关于页侧栏又带英文  | 1 failed, 7 passed in 6.25s
12/12 killed
8 passed in 5.31s
```

过程里两处要记下：「占位里没有分类图标」第一遍没被抓到（测试只看了攻略，变异删的是公告用的默认分支）；补测试后第一遍基线本身是红的（「没封面」也匹配到「公告没封面」），变异结果全是假的「被抓到」，改成按完整标题匹配、先确认基线绿再重跑。

浏览器：1280 截图看了资讯列表、分类筛选、文章页、搜索、隐私政策；手机 375 下 5 页 `scrollWidth` 都是 375。

## 设计偏差

无。

## 未完成 / 顺带发现 / 需要确认

- 本地开发库没有协议正文，隐私政策页只有标题；正文由 `load_legal_pages` 导入
- `c-pagehead__meta` 是 flex，文字和数字直接放进去会被间距拆开（普通页面「最后更新」、成员页「共 17 位成员」）。本轮改了普通页面，成员页在 084
- 开发服务器用 `--noreload` 启动，模板改了要重启才生效（截图时踩到一次）

## 改动文件

- 模板：`templates/components/post_card.html`（新）、`templates/components/category_wash.html`（新）、`templates/components/article_row.html`（删）、`templates/components/about_side.html`、`content/templates/content/{article_index_page,article_page,standard_page,submit,home_page}.html`、`search/templates/search/results.html`
- 样式：`assets/css/input.css`
- 测试：`content/tests/test_editorial_pages.py`（新）
- 文档：`docs/design.md`
