# 062 实现报告

## 结论

**完成。** 赛事、战队、内战详情页按设计 13.14 的表输出各自的分享信息；站点地图补上了内战活动。`content/seo.py` 里过时的「以后再接」注释删掉。

## 原来的样子

这三类页面只在模板里改了 `<title>`。`<meta name="description">`、规范网址、`og:title`、`og:description`、`og:image`、`og:url` 走的是全站默认的上下文处理器（标题是站名，描述是站点简介）——**在 QQ 群里贴一个赛事链接，预览出来和首页一样。**

`content/seo.py` 的注释写着「Extension point for later milestones: tournament / team / scrim」，`build_seo()` 的注释写着「callers should pass those kinds when those pages exist (M3/M4/M6)」。第五处「以后再接」没接上的占位。

## 实现

| 页面 | 标题 | 描述 | 图片 | 规范网址 |
|---|---|---|---|---|
| 赛事详情 | 赛事名称 | 简介（空的话用站点简介） | 封面 | 详情页地址 |
| 战队主页 | 战队名称 | 简介（同上） | 队标 | 同上 |
| 内战详情 | 活动名称 · 开始时间（北京时间，如「5月3日 19:30」） | 规格 · 已报名 N 人 | 默认分享图 | 同上 |

内战的报名人数会变，057 已经让报名、取消报名触发详情页重新生成，所以静态页里的人数跟得上。

站点地图：用 `scrims.services.public_scrims()`（已发布的和 30 天内结束的），草稿和已取消的不列。

## 测试

`content/tests/test_share_metadata.py`，5 条：从页面 HTML 里取出 `og:*`、`description` 和规范网址逐项比对；赛事和战队带真图片，检查 `og:image` 是绝对地址；赛事没有简介时回到站点简介；站点地图里有公开的内战、没有草稿和已取消的。

## 变异

```
✓ 被抓到 赛事不传简介 | 1 failed, 4 passed in 0.32s ['test_a_tournament_previews_with_its_name_summary_and_cover']
✓ 被抓到 赛事不传封面 | 1 failed, 4 passed in 0.28s ['test_a_tournament_previews_with_its_name_summary_and_cover']
✓ 被抓到 赛事用站名当标题 | 1 failed, 4 passed in 0.32s ['test_a_tournament_previews_with_its_name_summary_and_cover']
✓ 被抓到 战队不传简介 | 1 failed, 4 passed in 0.29s ['test_a_team_previews_with_its_name_description_and_logo']
✓ 被抓到 战队不传队标 | 1 failed, 4 passed in 0.34s ['test_a_team_previews_with_its_name_description_and_logo']
✓ 被抓到 内战不传分享信息 | 1 failed, 4 passed in 0.30s ['test_a_scrim_previews_with_its_time_format_and_signups']
✓ 被抓到 内战标题不带时间 | 1 failed, 4 passed in 0.32s ['test_a_scrim_previews_with_its_time_format_and_signups']
✓ 被抓到 站点地图不列内战 | 1 failed, 4 passed in 0.31s ['test_the_sitemap_lists_public_scrims_only']
8/8 被抓到，全部还原
```

规范网址这一项没做变异：不传的话 `build_seo` 会用 `request.path` 拼出一样的地址，直接访问时结果相同。显式传入是为了带查询参数访问时也指向干净的地址。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
235 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python -m pytest -q
829 passed in 52.87s
```

061 推送后的 CI：`success 061: 有有效报名的战队不能解散`。

## 改动文件

```
tournaments/views.py、teams/views.py、scrims/views.py   分享信息
content/views.py                                       站点地图加内战
content/seo.py                                         删掉过时注释
content/tests/test_share_metadata.py                   新建，5 条
handoff/STATUS.md
handoff/rounds/062-share-metadata/
```
