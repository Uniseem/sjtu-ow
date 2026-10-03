# 109 默认封面图库（官方图）（报告）

## 经过

1. 用户要照英雄形象画封面 SVG。我在临时目录画了五张剪影样张（莱因哈特屏障、天使、源氏夜樱、猎空闪现、推车团战），截图给用户，没进仓库
2. 用户：「这个太粗糙了。需要你对着官网或者游戏截图复刻的」。打开官网英雄页看参考：只有半身立绘，没有全身图；守望先锋 Wiki 被 Cloudflare 的人机验证拦住，没有去绕
3. 跟用户说明手写 SVG 的上限和复刻官方图的版权问题，给三个方向，用户选「官方图库」
4. 用户说「先给我看下效果」，我问能不能从官网英雄页下载 8 张页头立绘（文件名、来源、大小都列了），用户同意「下载，放本机和演示站」

## 做了什么

1. **设计 v6.7**：13.2.5 表格两行、新增「默认封面图库」一段；细节文档 v6.7（6.1、6.2 的图）；附录 D
2. **`core/covers.py`**（新）：`DEFAULT_COVER_COLLECTION = "默认封面"`；`load_pool()` 取这个集合里的图（按 id 排、缩略图一起取）；`index()` 用占位图同一个规则 `(ID + 偏移) mod 张数`；`pick()`
3. **`content/services.py`** 的 `ensure_default_cover_collection()`，`init_site` 调用
4. **上下文处理器** `core.context_processors.cover_pool`：每页一个惰性的图库，不用就不查
5. **模板标签** `{% cover_fallback obj "fill-WxH…" "类名" lazy=True %}`（`core/templatetags/ow.py`）：图库里有图就出那张的缩略图，加 `c-drift c-drift--N`（N 按对象编号轮换 1–4）；没有就出原来的占位图；宽高取自裁切参数
6. **6 个模板**换成这个标签：文章卡片、赛事卡片、文章页大封面、首页大图卡、赛事详情横幅、内战详情横幅
7. **样式**：`.c-drift` 四种推拉（`ow-drift-1` … `-4`，22–30 秒来回，只动 `scale` 和 `translate`，和卡片悬停的 `transform: scale(1.03)` 叠加）
8. **全站重新生成**：`content/signals.py` 里图片保存前记下原来的集合，保存后（进了、改了、离开图库）和删除后（在图库里）调用新的 `prerender.request_all_soon()`：和单页一样 30 秒合并（缓存 `add` 原子地占位），批量上传只排一次全量生成
9. **测试**：`core/tests/test_cover_pool.py`（12 条）
10. **README**：默认封面图库一条
11. **本机和演示站**：从官网 8 个英雄页（莱因哈特、天使、源氏、猎空、D.Va、安娜、卢西奥、黑百合）取页头立绘 `2600_<英雄>.jpg`（2600px 宽，每张 157–274 KB，共约 1.8 MB），导入两边的「默认封面」，说明里写明来源和版权归暴雪娱乐。图片不进仓库

## 命令输出

变异（`mutate.py`，14 处）。第一次跑漏了「缩略图逐张查」：测试只放了 3 张图，10 张卡片最多也只用到 3 张图，查询数在图库张数那里封顶；改成 12 张（比卡片多），单独重跑抓到。改完测试后整组重跑：

```
baseline green, 11 tests
caught articles and tournaments share pictures -> test_each_object_keeps_its_own_pool_picture
caught any picture counts as a cover -> test_pictures_elsewhere_are_not_in_the_pool
caught thumbnails come one by one -> test_a_long_list_looks_at_the_pool_once
caught every card looks the pool up -> test_a_long_list_looks_at_the_pool_once
caught pool pictures stand still -> test_pool_pictures_drift_and_keep_the_spots_class_and_size
caught cards load at once -> test_pool_pictures_drift_and_keep_the_spots_class_and_size
caught an empty pool shows nothing -> test_an_empty_pool_falls_back_to_the_drawn_placeholder
caught a card skips the pool -> test_no_template_reaches_for_the_placeholder_directly
caught scrims skip the pool -> test_scrim_banners_take_a_pool_picture
caught a picture leaving the pool is missed -> test_changes_to_the_pool_regenerate_the_site
caught a deleted picture is missed -> test_changes_to_the_pool_regenerate_the_site
caught every upload regenerates everything -> test_a_batch_of_uploads_regenerates_once
caught init_site makes no pool -> test_init_site_makes_the_pool
caught the drift fights the hover zoom -> test_the_drift_moves_only_scale_and_translate
restored and green; missed: none
```

整组检查（开发服务器停着）：

```
All checks passed!
274 files already formatted
No changes detected
System check identified no issues (0 silenced).
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1274 passed in 250.96s (0:04:10)
```

本机导入和检查（开发服务器、内置浏览器）：

```
added 8 | pool now 8
```

```
{"animation": "ow-drift-2 30s alternate", "cls": "c-cover__img c-drift c-drift--2", "scale": "1.0453", "src": "cover-ana.2e16d0ba.fill-2400x1200-c50.webp", "translate": "-1.15244% 0.493901%"}
```

（文章页大封面在推拉的半路，缩略图是 WebP。）

演示站部署（拉取 108，传上 109 的 15 个文件并转成 LF）：

```
dfcc355 108: 加载条在新页面上走满再淡出（设计 v6.6）
17
 Image sjtu-ow-web Built 
 Image sjtu-ow-worker Built 
sjtu-ow-web 7 seconds ago
sjtu-ow-worker 7 seconds ago
 Container sjtu-ow-worker-1 Started 
proxy Up 5 hours
web Up 20 seconds (healthy)
worker Up 20 seconds
已确保图片集合：投稿图片
已确保图片集合：默认封面
```

```
added 8 | pool now 8
全量生成完成：成功 46，失败 0，删除 0；目录占用 1599 KB
/news/: drift=12
/: drift=5
/news/push-map-guide/: drift=4
/tournaments/1/: drift=1
/scrims/: drift=0
/media/images/cover-dva.2e16d0ba.fill-960x540-c50.webp
200 image/webp 31934B
```

（内战列表本来没有图；内战详情页的横幅：`class="c-stage__img c-drift c-drift--2"`。）演示站截图（无头 Edge，1440 宽）：首页大图卡卢西奥、资讯卡片 D.Va 和源氏、内战页头猎空。

## 发现的问题（不在本轮修）

- 按英雄、地图打标签挑图（比如攻略文章配对应英雄）没做，设计里写了「以后」
- 图库加一张图，按位置取图的对象有一部分会换图（设计里写明是预期的）

## 未验证

- 管理员在后台上传到「默认封面」的界面流程（演示站还登录不了后台，等 HTTPS）；`request_all_soon` 在演示站上由真实上传触发的那次全量生成（导入用的是脚本，之后手动跑了全量生成）
- 手机上推拉动画的耗电（只动合成层属性，没有实测）
