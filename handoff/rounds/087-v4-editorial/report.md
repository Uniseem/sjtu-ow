# 087 刊物页按 v4.0 重做 报告

## 做了什么

1. **资讯列表**：栏目头的「我要投稿」改描边按钮；筛选挪进栏目头，`c-tabs` 改成下划线式（当前项 2px 深红下划线）；`c-media` 图片卡三列网格，列表上显示两行摘要；没有封面时灰底写分类名。`category_wash.html` 删除，`post_card.html` 改成 `c-media`，首页的资讯卡也改用它
2. **文章页**：`c-article` 44rem 正文栏居中；面包屑、分类、标题、作者行、头图（16:9）、正文、关联赛事、评论；正文后面「某分类的更多文章」一行 3 张图片卡（`RELATED_ARTICLE_COUNT` 4 → 3）。v3 的文末信息卡和右栏同栏目最新去掉
3. **普通页面**：同一正文栏；标题上方一行 `c-tabs` 切换关于、协议、隐私；`about_side.html` 删除
4. **搜索**：`c-searchbar` 改成 1px 控件描边的输入框；结果按类分组成 `c-rows` + `c-row--plain`，摘录用 `c-row__text`；搜索栏下的说明小字去掉，并进没有搜索词时的那段正文；分组标题旁的数量徽标去掉
5. **正文 `c-prose`**：引用改左侧 3px 竖线、不填底色；图片 8px 圆角；链接 `primary-text`
6. **样式**：删掉 v3 的列表行（`c-rowlist`）、文章卡（`c-post`）、文末信息（`c-byline`）；`c-empty`、`c-pager`、`c-tabs` 改 v4；赛事详情还在用的 `c-related`、几处还在用的 `c-count` 暂留（088、089 重做）
7. **账号安全页、样张页**：用到 v3 列表行的地方换成 `c-rows --plain`
8. 设计 13.2.6（`c-media` 列表加摘要、`c-row --plain`、`c-searchbar`、`c-article`）、13.2.7（关于三页的切换、搜索结果）先改文档再改代码

## 验证

变异（`handoff/rounds/087-v4-editorial/mutate.py`）：

```
BASELINE 63 passed in 22.72s
KILLED   没封面时又画渐变  | 1 failed in 2.50s
KILLED   资讯列表不显示摘要  | 1 failed in 3.86s
KILLED   筛选的当前项不是红色下划线  | 1 failed, 1 passed in 4.61s
KILLED   文章栏不居中  | 1 failed, 2 passed in 5.16s
KILLED   同栏目最新取 4 篇  | 1 failed, 31 passed in 18.14s
KILLED   关于三页不标当前页  | 1 failed, 3 passed in 5.76s
KILLED   搜索结果又带数量徽标  | 1 failed, 4 passed in 6.23s
KILLED   搜索栏下又写说明小字  | 1 failed, 4 passed in 6.22s
KILLED   引用又填底色  | 1 failed, 48 passed in 26.90s
9/9 killed
```

「引用又填底色」单独跑编辑页测试确认是专门那条抓到的：

```
FAILED content/tests/test_editorial_pages.py::test_quotes_are_a_rule_not_a_filled_block
1 failed, 9 passed in 7.48s
```

整组检查（Windows 本机，`PYTHONUTF8=1`）：

```
All checks passed!
247 files already formatted
Built production stylesheet '...\static\css\app.css'.
1003 passed in 238.79s (0:03:58)
No changes detected
System check identified no issues (0 silenced).
```

视觉（无头 Edge 截整页）：资讯列表、文章页（浅色、深色）、关于、搜索结果 1440 宽；`/news/`、`/news/demo-0/`、`/about/`、`/search/?q=内战`、`/me/` 375 宽 `scrollWidth` 都是 375。截图时发现文章页评论区上面有两条分隔线和一段空白（评论区自己带分隔线，外面又包了一层），已改成只由评论区自己画。

## 顺带发现的

- 本地开发库的「关于我们」没有正文，页面上只有标题（数据问题，不是模板问题）
- 搜索结果的摘录会把标题再重复一遍（搜索服务取摘录的方式），不在本轮范围
