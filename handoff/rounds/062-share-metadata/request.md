# 062 赛事、战队、内战的分享信息；站点地图补上内战

## 背景

059 找「以后再接」的占位时看到 `content/seo.py`：

```python
# Extension point for later milestones: tournament / team / scrim.
SHARE_KINDS = ("article", "tournament", "team", "scrim", "other")
```

`build_seo()` 的注释也写着「Tournament / team / scrim callers should pass those kinds when those pages exist (M3/M4/M6)」。**M3、M4、M6 都做完了，没有一个接上。** 这三类详情页只在模板里改了 `<title>`，`<meta name="description">`、规范网址和 `og:title`、`og:description`、`og:image`、`og:url` 全是全站默认。

设计 13.14 说社团链接主要在 QQ 群、微信里传播，「链接预览是否好看会直接影响点击」，并给了一张表：

| 页面 | 标题 | 描述 | 图片 |
|---|---|---|---|
| 赛事详情 | 赛事名称 | 简介 | 封面 |
| 战队主页 | 战队名称 | 简介 | 队标 |
| 内战活动详情 | 活动名称 + 开始时间 | 规格和报名人数 | 默认分享图 |

同一节还要求站点地图列出「公开的文章、普通页面、赛事、战队、内战活动」，**内战没列**。

## 任务

1. 三个详情视图按上表传入分享信息；描述为空时回到站点简介（`build_seo` 已有的行为）
2. 规范网址用详情页自己的地址
3. 站点地图加上公开的内战活动，已取消和草稿的不列
4. 删掉 `content/seo.py` 和 `build_seo` 注释里过时的「以后再接」说法
5. 测试 + 变异

## 验收标准

本地四项检查干净，推送后 CI 绿；测试机上各页面的分享信息正确。
