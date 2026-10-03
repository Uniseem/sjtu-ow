# 107 图片减重与懒加载（报告）

## 做了什么

1. **设计 v6.5**：13.10 加「缩略图的格式」「懒加载」两条，附录 D
2. **`settings/base.py`**：`WAGTAILIMAGES_FORMAT_CONVERSIONS = {"png": "webp", "jpeg": "webp"}`、`WAGTAILIMAGES_WEBP_QUALITY = 80`
3. **分享图**（`content/seo.py` 的 `image_absolute_url`）：`fill-1200x630|format-jpeg`
4. **文章正文图片**（`content/templates/content/blocks/image.html`）：`loading="lazy"`
5. **测试**：新文件 `core/tests/test_images.py`（6 条）：PNG 和 JPEG 原图的缩略图都是 WebP、质量 80；透明的 PNG 转完还是透明；分享图是 JPEG；模板里每张图要么懒加载、要么带首屏的标记（`c-stage__img`、`c-cover__img`、`c-feature__img`、战队主页队标 `fill-288x288`），首屏的图不能懒加载
6. **README**：升级到 107 及以后清一次旧缩略图，核对清掉的条数
7. **演示站**：升级到 106 + 107（拉取 106、传上 107 的三个文件并转成 LF、构建、`up -d`），清旧缩略图、全量生成；本机开发库也清了一次

## 命令输出

变异（`mutate.py`，7 处）：

```
baseline green, 5 tests
caught PNG thumbnails stay PNG -> test_thumbnails_are_webp_whatever_was_uploaded[PNG]
caught JPEG thumbnails stay JPEG -> test_thumbnails_are_webp_whatever_was_uploaded[JPEG]
caught WebP quality drifts -> test_thumbnails_are_webp_whatever_was_uploaded[PNG]
caught share images become WebP -> test_share_images_stay_jpeg
caught article pictures load at once -> test_pictures_below_the_first_screen_load_lazily
caught a member card loads at once -> test_pictures_below_the_first_screen_load_lazily
caught the article cover loads lazily -> test_first_screen_pictures_are_not_lazy
restored and green; missed: none
```

整组检查（开发服务器停着）：

```
All checks passed!
272 files already formatted
No changes detected
System check identified no issues (0 silenced).
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1258 passed in 207.98s (0:03:27)
```

演示站构建（这次不加 `-q`，确认镜像是新的）：

```
0150cac 106: 换页时的加载条和不闪、不弹入的过渡（设计 v6.4）
 3 files changed, 7 insertions(+), 2 deletions(-)
#15 11.80 Built production stylesheet '/app/static/css/app.css'.
 Image sjtu-ow-web Built 
 Image sjtu-ow-worker Built 
sjtu-ow-web 8 seconds ago
sjtu-ow-worker 8 seconds ago
```

第一次清旧缩略图后，成员页大图已经是 WebP，小图还是 PNG：

```
Successfully processed 74 rendition(s)
全量生成完成：成功 46，失败 0，删除 0；目录占用 1591 KB
50 images on /members/, total 1403 KB
fill-400x400 18220B image/webp
fill-176x176 49608B image/png
```

查库：PNG 的记录 id 是 131–172（昨天建的），新生成的 WebP 是 221–276，说明第一次有 41 条没删掉（命令的错误打在 stderr，被 `tail` 截掉了；时间上是 worker 刚重启、可能锁着数据库）。再跑一次：

```
Purging 129 rendition(s)
Successfully processed 129 rendition(s)
```

全量生成后：

```
全量生成完成：成功 46，失败 0，删除 0；目录占用 1591 KB

Counter({'webp': 103, 'jpg': 6})
/members/: 50 images, 505 KB, png left: 0
/: 8 images, 24 KB, png left: 0
/news/: 10 images, 29 KB, png left: 0
/teams/: 6 images, 18 KB, png left: 0
```

（6 个 JPEG 是分享图。成员页从改之前的 4276 KB 到 505 KB；一张 400px 名片从 214137 字节到 18220 字节。）

## 回答用户的问题

「你是不是没做懒加载？」：做了，21 处里 11 处懒加载；没懒加载的 10 处里 9 处是首屏的图（本来就不该懒加载），漏的是文章正文图片，本轮补上并加了测试。慢的主要原因是图片太大，见上面的数字。

## 发现的问题（不在本轮修）

- `wagtail_update_image_renditions` 在别的进程写库时会有几条删不掉，只在 stderr 里说；README 里写了要核对条数
- 1280px 左右页头导航折行（106 已记）

## 未验证

- 微信、QQ 里分享链接时的预览图（分享图是 JPEG，但没有实际在聊天软件里测）
