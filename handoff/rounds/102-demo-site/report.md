# 102 对外演示站（报告）

## 做了什么

1. **代码先上服务器**：用户要先部署，101 那时还没提交（全量测试在跑），把工作区里改过和新加的 33 个文件打成包传过去、`build`。101 提交推送后，服务器上 `git checkout -- .`、删掉包里带来的未跟踪文件、`merge --ff-only`，现在停在 `38674cb`，工作区只剩本机专用的两个文件
2. **演示库**：本机迁移到 `accounts/0006`，`manage.py backup --no-upload`（4.3 MB，邮箱都是 `demo.example.com`、SMTP 没配，恢复后不会真的发信）。服务器上先确认库里没有用户（0 个，没有用户自己建的账号会被冲掉），停 `web`、`worker`，`restore` 演练、正式恢复
3. **`restore` 恢复 media 失败**：见下面的输出。数据库换好了，media 被删空、没复制回来，`prerendered` 也没清。手工从备份里把 `media/` 复制进数据卷，再 `prerender --clear`、`prerender`
4. **头像**：先下了 40 张 DiceBear lorelei（CC0）导进本机库；用户看了说要「二次元动漫的那种」，选了 nekos.best。`anime_avatars.py` 在服务器的 web 容器里取 40 张（waifu 14、neko 12、husbando 10、kitsune 4），焦点设在图的上部（竖图 28%、横图 40%）让方形裁切落在脸上，换掉全部头像、删掉旧图。图片标题写「头像 · 昵称 · 画师 X」，说明里写画师主页和出处。本机库还是 lorelei，没换
5. **内容**：`enrich_demo.py`，按地址找文章、按标题找赛事和内战，重复跑不会重复加。本机跑通后在服务器上跑，再全量生成
6. **文档**：`AGENTS.md`「第二台」加「对外演示站」一行、在服务器上跑脚本的写法；「已知的坑」加三条（`restore` 的 media、Windows 上 `shell <`、本机推送 403）

## 命令输出

上传、拉代码、构建：

```
5432a7b 100: v6.0 部署到 169.58.217.180:22887，记录部署方式
35
 Image sjtu-ow-worker Building 
 Image sjtu-ow-web Built 
 Image sjtu-ow-worker Built 
BUILD_OK
```

恢复演练和确认服务器库是空的：

```
FIELD_ENCRYPTION_KEY 校验通过。
  - 用备份里的数据库替换 /app/data/db.sqlite3
  - 删除 WAL 文件：/app/data/db.sqlite3-wal, /app/data/db.sqlite3-shm
  - 恢复 media 到 /app/media
  - 清空 /app/prerendered
这是演练，什么都没有改。加 --yes 才会执行。
```

```
users: 0 superusers: 0
```

正式恢复（尾部）、迁移、启动、预渲染：

```
  File "/usr/local/lib/python3.13/shutil.py", line 658, in _rmtree_safe_fd
    os.rmdir(name, dir_fd=dirfd)
    ~~~~~~~~^^^^^^^^^^^^^^^^^^^^
OSError: [Errno 16] Device or resource busy: PosixPath('/app/media')

Running migrations:
  No migrations to apply.
 Container sjtu-ow-web-1 Started 
 Container sjtu-ow-worker-1 Starting 
 Container sjtu-ow-worker-1 Started 
proxy Up 36 minutes
web Up 20 seconds (healthy)
worker Up 20 seconds
全量生成完成：成功 37，失败 0，删除 0；目录占用 1120 KB
```

media 是空的、手工补回：

```
total 8
drwxr-xr-x 2 root root 4096 Oct  2 21:35 .
drwxr-xr-x 1 root root 4096 Oct  2 21:35 ..
0
```

```
1625
11M	/app/media
```

```
已清空静态文件（原有 37 个页面记录）
全量生成完成：成功 37，失败 0，删除 0；目录占用 1128 KB
```

动漫头像：

```
api results: 40
avatars replaced: 40
old avatars deleted: 40
```

```
全量生成完成：成功 37，失败 0，删除 0；目录占用 1130 KB
113M	/app/media/original_images
40
     12 200
0
```

（成员页 12 张名片大图都是 200，页面里旧头像的引用 0 处。）

内容补全，本机第一次用 `manage.py shell < 文件`，Windows 上退回交互式控制台逐行执行，空行处断开（节选）：

```
>>> ... ...   File "<console>", line 3
    print("tournaments updated", len(TOURNAMENTS))
    ^^^^^
SyntaxError: invalid syntax
```

改用 `shell -c "exec(open(...).read())"` 重跑（脚本可重复执行，第一次跑了一半的部分不会重复）：

```
articles created 0 updated 21 | total 21
comments added 52 | total 70
tournaments updated 5
friendly scrim exists | signups 8 (+8)
mottos filled; users without motto: 0
```

本机逐页请求：

```
37 pages; not 200: []
final: toc | image | quote
```

服务器：

```
articles created 8 updated 13 | total 21
comments added 52 | total 70
tournaments updated 5
friendly scrim created | signups 8 (+8)
mottos filled; users without motto: 0
全量生成完成：成功 46，失败 0，删除 0；目录占用 1553 KB
```

从本机访问演示站：

```
13 checked, 0 not 200
新人友好场
12
anime-10.484ce5e8.fill-88x88
anime-13.e510092f.fill-176x176
anime-13.e510092f.fill-88x88
anime-19.7724ef1e.fill-88x88
anime-22.ae1ae53c.fill-88x88
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"}, "disk": {"ok": true, "detail": "free space 74.0%"}
```

服务器代码对齐：

```
38674cb 101: 头像能显示图片（设计 v6.1）
?? deploy/Caddyfile.vps
?? deploy/docker-compose.vps.yml
```

## 发现的问题（不在本轮修）

- **`restore` 在 Compose 部署里恢复不了 media**（上面的输出）。`shutil.rmtree(media)` 删到挂载点本身时失败；应该只清空目录里的东西，再 `copytree(..., dirs_exist_ok=True)`。这条路径（备份恢复）是设计 16.7 的灾备手段，测试是在普通目录里跑的，所以一直是绿的。下一轮修，要加一条「`MEDIA_ROOT` 是不能删的目录」的测试
- **演示备份带了测试留下的图**：本机 `media/original_images/` 里有几十张 `tournament-cover_*.png`（101 报告里说的测试往项目 `media/` 写图），跟着备份上了服务器，没有被引用，占地方不大

## 未验证

- 演示站在域名和 HTTPS 下的样子（等用户配反向代理）
- 后台登录（等用户自己建管理员）
- worker 事件触发的生成：评论和文章发布时会排预渲染任务，这次之后又跑了全量生成，没有单独看事件触发的那几页
