# 182 上线准备：恢复演练和转正式站的步骤（报告）

## 结论

**能上线，代码这边没有挡着的事。** 挡着的是四件只有用户能给的东西：发信账号、协议里社团要定的几项事实、演示数据清不清、建超级管理员。写在 STATUS「上线计划 → 你那边」。

## 演示站逐项核对

在演示站上跑了后台「上线清单」（`core.admin_setup.setup_checks`）和几项环境检查：

```
== 上线清单
  --  [必做] 邮件（SMTP）：还没配置。注册要验证邮箱，没有邮件就没有人能注册、找回密码。在全站设置里填 SMTP 服务器和发件地址，再点「发送测试邮件」。
  --  [必做] 用户协议：正文里还有 4 处【】要社团填写（运营方、联系方式、生效日期等）。
  --  [必做] 隐私政策：正文里还有 8 处【】要社团填写（运营方、联系方式、生效日期等）。
  --  [建议] AI 内容审核：服务器没有设置环境变量 MODERATION_API_KEY（或自建服务的 MODERATION_BASE_URL），AI 审核不会运行。写进 .env 后重启 web 和 worker。
  --  [建议] 异地备份：加密密钥已设置，全站设置里「备份上传到对象存储」还没开。填好对象存储后点「测试对象存储」，测通了再打开。
  OK  [建议] 内容编辑：已有人负责。
  --  [建议] 关于我们：还是空的。页脚每页都链到它，写几句社团介绍和联系方式。
  --  [建议] 首页和分享信息：还没填：站点简介、QQ 群链接、首屏图片。站点简介用在搜索结果和链接预览里，QQ 群链接是首页的「加入」按钮。
  OK  [建议] 默认封面和默认头像：图库里有图。
  --  [建议] 测试环境标记：页面顶部有「测试环境」横幅、禁止搜索引擎收录。正式上线前去掉 .env 里的 TEST_ENVIRONMENT 并重启。
== 账号
  超级管理员: 0  用户总数: 40  demo.example.com 邮箱: 40
== 环境
  TEST_ENVIRONMENT = True
  PRERENDER_ENABLED = True
  SITE_URL = https://sjtu.ow-shanghaiuniversity.com
  DEBUG = False
  MODERATION_API_KEY 设置了: False
  BACKUP_ENCRYPTION_KEY 设置了: True
  数据库: /app/data/db.sqlite3 4.5 MB
  media: 216.3 MB
```

服务器：`ipinfo.io` 查 169.58.217.180 是法国 Lauterbourg，`AS51167 Contabo GmbH`（隐私政策里「服务器所在国家、服务商」两处就填这个）。磁盘 148G 用了 112G（还有 31G，上面还有别的服务）。定时任务 `/etc/cron.d/sjtu-ow` 在，备份卷里有北京时间今天 03:00 的一份。

外部资源：首页、资讯、战队、赛事、内战、注册页的 HTML 里没有任何指向别的站点的 `src` / `href`（国内打不开的字体、CDN 一个都没有）。

国内打开速度：用内置浏览器（在开发者本机，国内，没有缓存）打开首页，读 Navigation Timing：

```
"ttfb": 1019, "html_done": 1076, "dcl": 2782, "protocol": "h2", "transfer_kb": 110,
"encoded_css": [[19581, 19281, 92559], ...]
```

首字节 1.0 秒、DOMContentLoaded 2.8 秒，样式 92 KB 压缩成 19 KB。用 curl 逐个取资源时每个请求都要 1 秒多（3 KB 的文件也是），说明慢在往返延迟（国内 → 用户的反代 → 法国），不在体积。

## 恢复演练（测试机）

1. 照 README「生产 / 测试环境启动」从零搭站：克隆、生成三把新密钥、构建、启动。第一次我的脚本漏了 README 写的「先迁移再启动」，首页 500；补上 `migrate`、`createcachetable`、`init_site` 后首页、`/healthz` 都是 200。构建镜像约 2 分半
2. 演示站当天的备份 226 MB 经本机中转传到测试机，177 秒，sha256 两边一致（`0578575713…7fbe24`）
3. 恢复（`drill_restore.sh`，`--skip-key-check`：演示站的密钥不离开演示站，库里没有加密内容）：

```
[4s] restore
恢复完成。
注意：恢复的数据库比当前代码旧，还差 6 个迁移（core.0018_tournament_reminder, core.0019_broadcast_waits_for_publish, teams.0004_member_contact, teams.0005_captain_reminded_at, tournaments.0010_tournament_reminder……）。
[8s] migrate (the backup may be older than the code)
[11s] start
全量生成完成：成功 46，失败 0，删除 0；目录占用 1626 KB
[32s] check
/ 200 28992B
/news/ 200 27347B
/teams/ 200 19081B
/tournaments/ 200 16170B
/scrims/ 200 17902B
/members/ 200 82364B
/accounts/login/ 200 15817B
/healthz 200 276B
users 40 teams 7 articles 21 comments 70 images 478
[34s] done
```

演示站当时：`users 40 teams 7 articles 21 comments 70 images 478`，一致。备份是凌晨 3 点的，之后演示站升级过几轮，`restore` 照设计列出了差的迁移。

## 转正式站演练（测试机，恢复出来的站上）

```
[0s] 1. a last backup of the demo, copied out of the volume (backup prunes after 14 days)
已备份到 /app/backups/sjtu-ow-20261004-164650.tar.gz（215.6 MB）
[7s] 2. stop web and worker, empty the database, uploads and static pages
[9s] 3. a fresh database
[26s] 4. no more test banner
全量生成完成：成功 9，失败 0，删除 0；目录占用 194 KB
[38s] 5. check
/ 200
/news/ 200
/teams/ 200
/accounts/signup/ 200
/robots.txt 200
/healthz 200
robots: User-agent: * Disallow: /admin/ Disallow: /me/ Disallow: /accounts/ Disallow: /_
banner on home: 0
users 0 teams 0 articles 0 images 0
[39s] done
```

空站点的首页：各区块显示「最近没有安排」「还没有文章」「还没有公告」，数字条是 0，页脚、导航正常。

步骤写进 README「演示站转正式站」（命令换成演示站的 `$C`），包括怎么回到演示数据。演练完把测试机上的容器、卷、镜像和两份备份都删了（备份里有演示账号的邮箱）。

## 没做

- **没有动演示站**：转换要等用户定演示数据怎么处理，而且没有发信账号时转成正式站也没人能注册
- 外部监控没设：要一个能发提醒的地方（邮箱、QQ），等用户
- 恢复演练用的是新密钥加 `--skip-key-check`，没有验证「用原来的 `FIELD_ENCRYPTION_KEY` 解开加密字段」这一步（演示站没存加密内容，测了也看不出）；这一步在 `core/tests/test_ops_commands.py` 有测试
