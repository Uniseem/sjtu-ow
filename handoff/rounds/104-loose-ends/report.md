# 104 101–103 顺带发现的四个问题（报告）

## 做了什么

1. **设计 v6.2**：3.8 注销时头像、个人宣言、常用位置清空，审核记录里的昵称和宣言快照一起删；13.13.4「用户修改昵称」一行扩成公开资料，加上离开过的战队主页（101 已实现，表里补上）和「有已发布文章时的首页和文章栏目页」；16.7 恢复第 2 步改成先放上传文件、再换数据库；附录 D
2. **注销**（`accounts/services.py` 的 `delete_account`）：清空 `motto`、`main_role`、`flex_roles`；删审核记录时 `target_type` 包括 `motto`
3. **作者的列表卡片**（`refresh_nickname_pages`）：这个人有已发布、公开的文章时，调用 `content.signals.refresh_listings("article")`，和发布文章时刷新的范围一样（首页、各文章栏目页）；没写过文章的人不会触发整个首页重新生成
4. **测试不写项目的 `media/`**：`conftest.py` 加一个自动生效的 fixture，每个测试的 `MEDIA_ROOT` 是一个临时目录（自己设了的测试照旧覆盖）；新测试 `core/tests/test_isolation.py`。本机和演示站上测试留下、没有被任何图片或缩略图引用的文件删掉了（只删 `original_images/`、`images/` 里没被引用的）
5. **恢复的顺序**（`restore`）：先清空并复制 media，再关连接、删 WAL、换数据库、清 `prerendered`；复制 media 出错时抛「恢复 media 失败……数据库还没有替换；解决问题后重新运行同一条命令」。演练时打印的步骤也按新顺序

## 命令输出

变异（`handoff/rounds/104-loose-ends/mutate.py`，8 处）：

```
baseline green, 5 tests
caught deletion keeps the motto -> test_deleting_clears_the_public_profile
caught deletion keeps the main position -> test_deleting_clears_the_public_profile
caught deletion keeps the other positions -> test_deleting_clears_the_public_profile
caught the review queue keeps the motto -> test_deleting_drops_the_review_queues_copies_of_the_nickname
caught listings are not refreshed for authors -> test_an_authors_new_face_reaches_the_homepage_and_listings
caught listings are refreshed for everyone -> test_an_authors_new_face_reaches_the_homepage_and_listings
caught tests write to the project media -> test_uploads_in_tests_never_reach_the_project_media_folder
caught the database goes in before the uploads -> test_a_failed_upload_copy_leaves_the_database_alone
restored and green; missed: none
```

（「测试写进项目 media」那处变异关掉了隔离，测试真的往本机 `media/` 写了一张 `isolation*.png`，下面清理时一起删了。）

本机 `media/` 里没被引用的文件：

```
media root: D:\claude\sjtu-ow\media
referenced files: 209 | orphans: 1539 | bytes: 4628048
orphan name prefixes: [('tc', 300), ('cover', 290), ('HengFu', 178), ('hero', 135), ('cv', 132), ('article-cover', 105), ('logo', 102), ('tournament-cover', 102), ('c', 90), ('DuiWuHengFu', 72), ('back', 32), ('isolation', 1)]
deleted 1539
```

演示站（102 的备份带过去的）：

```
media root: /app/media
referenced files: 209 | orphans: 1505 | bytes: 4521787
orphan name prefixes: [('tc', 295), ('cover', 286), ('HengFu', 173), ('hero', 132), ('cv', 129), ('article-cover', 102), ('logo', 99), ('tournament-cover', 99), ('c', 88), ('DuiWuHengFu', 70), ('back', 32)]
deleted 1505
117M	/app/media
```

整组检查（开发服务器停着）：

```
All checks passed!
269 files already formatted
No changes detected
System check identified no issues (0 silenced).
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1235 passed in 147.77s (0:02:27)
```

## 发现的问题（不在本轮修，105 处理）

- **预渲染页没有安全响应头**：Caddy 直接返回的预渲染页面没有内容安全策略、`X-Frame-Options`、`nosniff`、`Referrer-Policy`（同一页走 Django 时都有）。前台大部分访问都是预渲染页，等于设计 15.2 的内容安全策略和防嵌入在这些页面上没生效
- **Caddy 2.10.2 的 `precompressed` 返回 206**：浏览器每次都带 `Accept-Encoding`，静态文件和预渲染页于是都是 `206 Partial Content` 加完整内容。Chromium 照样缓存，别的浏览器和中间的代理不一定
- **上传图片没有缓存头**：设计 13.10 写的缩略图一年缓存没有落到 Caddyfile 里，只有字体文件有
- **演示站的 canonical 是 `http://localhost:8000/…`**：库是本机恢复过去的，Wagtail 站点记录还是本机地址；`init_site` 会按 `SITE_URL` 改回来，102 漏跑了

## 未验证

- 演示站上的 104 代码要等推送后拉取、重建（见 STATUS）
