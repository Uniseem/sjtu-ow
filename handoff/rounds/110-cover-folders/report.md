# 110 封面图库分文件夹、扩充官方图、人物构图（报告）

## 做了什么

1. **设计 v6.8**：13.2.5「默认封面图库」加「分文件夹」「构图」两条；附录 D 一行
2. **图库包括子文件夹**（`core/covers.py`）：`pool_root()` 找最上层的「默认封面」；`load_pool()` 改成按集合路径前缀取图（`collection__path__startswith`），默认封面和它下面任意深的子集合都算，旁边的集合（投稿图片）不算；`in_pool()` 判断一个集合在不在图库里
3. **全站重新生成**（`content/signals.py`）：图片进出图库的判断改用 `in_pool()`，图移进移出子文件夹也触发（原来只认「默认封面」这一个集合）
4. **测试**：`core/tests/test_cover_pool.py` 加两条（子文件夹里的图在图库里、旁边的集合不算；图移进移出子文件夹各触发一次全站生成），共 14 条
5. **README**：默认封面图库那条加分文件夹、上传前怎么裁
6. **收集官方图**（脚本在 `tools/`，图片不进仓库）：
   - `crawl_v2.py`：官网繁中新闻全部列出 668 篇，去掉更新说明、电竞、开发者问答等 115 篇，剩 553 篇；收集文章里暴雪 CMS 的大图，连同图片的 alt 和图前面的文字，共 1729 张不重复的图
   - `fetch_pictures.py`：每张先读前 128 KB 拿到尺寸，留下横图、宽至少 1500、宽高比 1.25–2.7 的 669 张，下载（733.7 MB）
   - `sheets.py`：拼成每张 48 格、标号的对照图，一共 14 张对照图，逐格看过：去掉界面截图、数据图表、文字多的宣传图、设定稿（白底、灰底的三视图）、图标、带大 logo 的合作图、真人活动照片和赛事选手照，留下 326 张；按 16×9 平均哈希去掉 15 张同图不同地址的，剩 311 张
   - **分文件夹**：图片 alt 里大多是原始文件名（`WEB_S17_Mythic_Dva_ux.png`、`KerriganWidowmaker.png`），`alt_heroes.py` 从里面认英文英雄名（合集、群像类文件名不认）；认不出的按我看图时选的文件夹，单人但认不准是谁的放「群像与活动」。另加 109 用过的官网 53 个英雄页页头立绘，每个英雄至少一张
   - 结果：**364 张、56 个文件夹**：53 个英雄文件夹共 167 张（天使、探奇 8 张，源氏 7 张，最少的 1 张），群像与活动 131 张，地图场景 53 张，海报 13 张。清单（每张的文件夹、原图地址、出处文章）在 `manifest.json`
7. **构图**（`make_pool.py`）：主体位置按图的细节分布估（边缘检测后取最强的 15% 求重心，避开四边的 logo 和界面条）；裁成 16:9、最宽 2400，主体放在横向 58%（主体本来在左半边的放在 42%）、纵向 42%，需要时最多放大到原来 16:9 窗口的 78%。364 张主体横向位置中位数 0.58，范围 0.34–0.68。导入时焦点设为整宽、半高、中心在主体高度：裁成 2400×900 这类更窄的横幅时只上下裁、不切人，`c50` 也不会再拉近
8. **本机和演示站导入**（`import_pool.py`）：去掉 109 的 8 张旧图（它们在「默认封面」本身），建 56 个子文件夹，按固定的打乱顺序导入。第一次按文件夹顺序导入，截图发现资讯页的文章卡全是英雄页立绘：图库按 ID 排、按 `(ID + 偏移) mod 张数` 取，演示文章的 ID 小，正好全落在最先导入的 53 张立绘上。改成打乱后导入（`random.Random(110)`），相邻的文章取到不同文件夹的图；取图规则不变。演示站全量生成，截图看构图

## 命令输出

变异（`mutate.py`，3 处）：

```
baseline green, 2 tests
caught folders under the pool are left out -> test_the_folders_under_the_pool_are_in_it
caught a collection beside the pool counts -> test_the_folders_under_the_pool_are_in_it
caught moves into a folder are missed -> test_moving_a_picture_into_or_out_of_a_folder_regenerates
restored and green; missed: none
```

整组检查（开发服务器停着）：

```
All checks passed!
274 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
```

```
1276 passed in 153.65s (0:02:33)
```

收集和下载（抓取时的终端输出没留下，第一行是事后从 `news_v2.json` 重新数的；列出的 668 篇是抓取脚本当时打印的）：

```
articles kept: 553 | pictures: 1842 | unique: 1729 | errors: 0
unique pictures: 1729
usable by size: 669
downloaded: 669 | MB: 733.7
chosen 326 duplicates 15 selected 311
pictures: 364 folders: 56
```

本机导入（第二次是打乱顺序重导）：

```
round 109 banners removed: 8
added 364 | folders 56 | pool now 364
round 109 banners removed: 0
removed to import again: 364
added 364 | folders 56 | pool now 364
```

演示站（`build` 后镜像时间 `2026-10-03T08:29:10+02:00`，容器里 `core/covers.py` 有新代码）：

```
round 109 banners removed: 8
added 364 | folders 56 | pool now 364
全量生成完成：成功 46，失败 0，删除 0；目录占用 1602 KB
364 159
removed to import again: 364
added 364 | folders 56 | pool now 364
全量生成完成：成功 46，失败 0，删除 0；目录占用 1604 KB
```

`/app/media/original_images` 425 个文件（364 张图库 + 演示头像和种子图片），`/app/media` 共 208 MB：删掉的旧图连文件一起删了。

演示站截图（无头 Edge，1440 宽，浅色）：首页大图卡是半藏立绘，人在画面偏右、左边留给标题；资讯页 12 张卡片分别是动漫风插画、对战截图、皮肤宣传图、地图，不再是一排立绘；文章页大封面、赛事和内战横幅都是图库图，人物没被切掉。

## 没做 / 未验证

- 英雄文件夹的图不平均：官网新闻里有的英雄只出现在合集图里，单人图只有页头立绘一张
- 「群像与活动」里有一部分其实是单人图，看图认不准是谁的就放在这里，没有硬分
- 后台「设置 → 集合」里手动建子文件夹、上传到子文件夹的界面流程：演示站还登录不了后台（等 HTTPS），本机也没在浏览器里点过
- 深色模式和手机宽度下的构图没截图
- 1280 宽时页头导航折行（「首/页」）还没修，留到下一轮
