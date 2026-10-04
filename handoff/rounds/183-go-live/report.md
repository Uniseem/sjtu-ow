# 183 演示站转正式站（保留图片库）（报告）

## 做了什么

1. `export_images.py` / `import_images.py`：把图片库（行，不是文件）写成 JSON、在新库里按名字重建集合树再写回。本机先用开发库的副本演练：导出 478 张、64 个集合，导进全新的临时库后再导出，两份逐字段一致（`collections same: True`、`images same: True 478 478`），临时库删了
2. `go_live.sh`：在服务器上脱离连接跑（步骤见 `request.md` 和 README「演示站转正式站」）
3. 公网核对、上线清单核对
4. 服务器整理：删掉 `/root/go_live.sh`（有破坏性，仓库里留一份）；当初往演示站灌数据的 13 个脚本挪进 `/root/demo-era-scripts/`；备份卷里两份演示数据的备份删了（最终那份已拷到 `/root/sjtu-ow-backups/`）
5. README「演示站转正式站」改成实际做的版本；AGENTS.md「第二台」改成正式站；STATUS

不改网站代码。

## 命令输出

服务器上（`/root/go_live.log`，去掉了容器启停的行）：

```
[0s] 0. keep: .env, a last full backup copied out of the volume
已备份到 /app/backups/sjtu-ow-20261004-183751.tar.gz（216.2 MB）
-rw-r--r-- 1 root root 226691234 Oct  4 12:37 /root/sjtu-ow-backups/demo-final-20261004-123749.tar.gz
[10s] 1. export the image library
exported 478 images in 64 collections to /app/data/images-export.json
files missing on disk: 0 []
[13s] 2. stop web and worker; old database aside; drop thumbnails, font files, static pages
-rw-r--r-- 1 root root 4767744 Oct  4 10:37 demo-final.sqlite3
-rw-r--r-- 1 root root  244223 Oct  4 10:38 images-export.json
211M	/app/media/original_images
[17s] 3. a fresh database
  Applying wagtailusers.0015_userprofile_keyboard_shortcuts... OK
[46s] 4. the image library back
imported 478 images; collections now 64
[51s] 5. production: no test banner, containers recreated, every page generated
全量生成完成：成功 9，失败 0，删除 0；目录占用 195 KB
[204s] done
```

停下 web、worker 后 SQLite 已经把 WAL 合回主文件，数据卷里只有 `demo-final.sqlite3`。第 5 步里等健康检查的循环一直没等到 200（原因见下），走满 2 分钟才往下，所以总共 204 秒。

转换后在服务器上查：

```
users 0 teams 0 articles 0 comments 0 tournaments 0 scrims 0
images 478 collections 64
  默认封面 364
  默认头像 53
  头像 40
rendition ok: /media/images/cover-fb7ab7ca42_EEObooH.f47168c0.fill-400x225.webp 400 225
TEST_ENVIRONMENT False
  --  [必做] 邮件（SMTP）
  --  [必做] 用户协议
  --  [必做] 隐私政策
  --  [建议] AI 内容审核
  --  [建议] 异地备份
  --  [建议] 内容编辑
  --  [建议] 关于我们
  --  [建议] 首页和分享信息
  OK  [建议] 默认封面和默认头像
  OK  [建议] 测试环境标记
```

公网（本机访问域名）：

```
200 /
200 /news/
200 /teams/
200 /tournaments/
200 /scrims/
200 /members/
200 /accounts/signup/
200 /accounts/login/
200 /terms/
200 /privacy/
200 /about/
robots:
User-agent: *
Disallow: /admin/
Disallow: /me/
Disallow: /accounts/
Disallow: /_fragments/
Disallow: /_styleguide/
Disallow: /search/
Sitemap: https://sjtu.ow-shanghaiuniversity.com/sitemap.xml
banner on home: 0
noindex meta: 0
```

## 发现的问题：磁盘

`web` 容器显示 unhealthy，`/healthz` 返回 503：

```
{"status": "error", "checks": {"database": {"ok": true, "detail": "ok"}, "disk": {"ok": false, "detail": "free space 19.1% is at or below 20%"}, "worker_heartbeat": {"ok": true, "detail": "ok (19s ago)", "affects_status": true}, "task_backlog": {"ok": true, "detail": "ok", "affects_status": true}}}
```

服务器 158 GB 的盘用了八成（上面还跑着 WordPress 等），健康检查要求剩余大于 20%（设计 16.6）。转换前就在线上（182 查时 31 GB 剩余），这次的最终备份把它推过了线。删掉备份卷里两份重复的演示备份后是 19.35%，还差一点。

`docker system df`：镜像 68 GB（本项目 1.3 GB）、卷 0.7 GB、**构建缓存 19.5 GB**。按描述归类，本项目的构建缓存 150 条、15.56 GB（每次升级 `COPY . .` 那一层），别的项目 48 条、3.96 GB（一个 Next.js 应用）。试了 `docker buildx prune --filter id=<id>` 只删本项目的条目，删除量都是 0（条目互为父子，单条删不动）；整体 `docker builder prune` 会连别的项目的缓存一起清，属于 AGENTS.md 说的全局清理，没做，等用户决定。清掉的只是缓存，影响的只是下次构建要不要重新下载、安装。

网站本身不受影响：Docker 不会因为 unhealthy 重启容器，Caddy 也不看这个状态。以后接外部监控的话会一直报警。

## 没做

- 全站设置里的成立日期没带过去：2019-09-15 是 `seed_demo.py` 造的
- 「头像」集合（演示账号用的 40 张动漫插画）照用户说的保留在图片库里，现在没人用；不要的话在后台图片库里删
- 发信、协议、超级管理员：等用户
