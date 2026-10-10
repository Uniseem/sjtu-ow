# 265 实现报告

## 结论

完成。正式站 2026-10-10 09:30（柏林时间，北京 15:30）起回到旧站（Django），停机约 1 分钟（新栈停下到旧站的 Caddy 起来）；没有丢数据。第 10 节前四件的拍板写进了文档。

## 逐条结果

### 1. 只读核查（改任何东西之前）

- 在跑：新栈四个容器（`sjtu-ow-server/worker/web/proxy-1`），都是 259 用 `deploy/docker-compose.new.yml`、Compose 项目 `sjtu-ow` 起的
- **旧站的镜像没了**：新栈的 `web`（SSR）和旧站的 `web`（Django）同一个项目、同一个服务名，构建出的镜像都叫 `sjtu-ow-web:latest`，259 构建新栈时把旧的标签占了。所以回滚要重新构建旧站镜像（仓库里 Django 代码还在，Dockerfile 在仓库根）
- 旧站数据卷都在：`sjtu-ow_data`、`sjtu-ow_media`、`sjtu-ow_prerendered`、`sjtu-ow_static`、`sjtu-ow_backups`、`sjtu-ow_caddy_*`
- 旧库和割接前的快照逐字节一致：

```
9b0d53f77e1b8ce82b9a387a77148b034769617a6d511940fe7a294c08d90d79  /var/lib/docker/volumes/sjtu-ow_data/_data/db.sqlite3
9b0d53f77e1b8ce82b9a387a77148b034769617a6d511940fe7a294c08d90d79  /root/sjtu-ow-backups/legacy-final-20261009134549.sqlite3
('ok',) (1,) (335,)        ← integrity_check、用户数、最新迁移编号
```

- 新栈割接以后写进去的（回滚会丢的）：除了一条登录会话和导入时打的时间戳，什么都没有：

```
users [(1, 0, ...)]  sessions [(1, 1, ...)]  teams [(1, 0, ...)]  comments [(4, 0, ...)]
team_applications [(0, None, None)]  scrim_signups [(0, None, None)]  registrations [(0, None, None)]
email_codes [(0, None, None)]  audit_log [(0, None, None)]
```

（每行是「总数、割接以后新建的数、最晚的时间」；`pages`、`contacts` 各有 1 行「新建」是导入那一刻打的时间戳。）

- `.env` 里旧站的变量都在（`DJANGO_SECRET_KEY`、`DJANGO_ALLOWED_HOSTS`、`DJANGO_CSRF_TRUSTED_ORIGINS`、`SITE_URL`……），另有 260 加的 `BACKUP_KEEP_DAYS=0`
- 定时任务 `/etc/cron.d/sjtu-ow`：260 把备份、清理两条注释掉了，审核摘要那条删了；旧的预渲染等几条还开着（割接后它们 `exec` 进的是新栈的 `web`，那里没有 Python，一直失败）
- 磁盘 81%（剩 28 GB，19%），`/healthz` 的磁盘检查要剩 20% 以上，所以新栈、旧站的 `/healthz` 都是 503；可回收的大头是别的项目的镜像（texlive 等），本项目只有约 4 GB 构建缓存

### 2. 回滚

两段脚本（`scp` 上去、`setsid nohup` 脱离连接跑，AGENTS 的两条坑），原文在本轮目录 `rb-build.sh`、`rb-switch.sh`：

```
# rb-build.sh：旧站 Compose build web worker（新栈照跑）
Image sjtu-ow-worker Built
Image sjtu-ow-web Built
sjtu-ow-web:latest fd09ec1ac6e3 2026-10-10 09:28:51 +0200 CEST 1.3GB
```

```
# rb-switch.sh
== Sat Oct 10 09:30:00 CEST 2026 停新栈
 Container sjtu-ow-server-1 Stopped ...
== 新栈最后的库留一份           → /root/rollback-check/newdata-final/
== 起旧站
 Container sjtu-ow-web-1 Started / sjtu-ow-proxy-1 Started / sjtu-ow-worker-1 Started
== 等 web 健康                  → unhealthy（只因磁盘检查，见上）
== Sat Oct 10 09:35:15 CEST 2026 全量预渲染
全量生成完成：成功 12，失败 0，删除 0；目录占用 278 KB
```

`docker compose down` 没带 `-v`：新栈的卷（`sjtu-ow_sjtuow_data`、`sjtu-ow_sjtuow_assets`）和镜像都还在。

### 3. 定时任务

改前的存到 `/root/rollback-check/cron-before-265`，换成割接前的那份（`/root/sjtu-ow-backups/cron-before-194`，和割接前的内容一致）：

```
10c10
< # 0 21 * * * root $DC exec -T web python manage.py backup
> 0 21 * * * root $DC exec -T web python manage.py backup
12c12
< # 0 22 * * * root $DC exec -T web python manage.py cleanup_old_data
> 0 22 * * * root $DC exec -T web python manage.py cleanup_old_data
19a20
> 30 3 * * * root $DC exec -T web python manage.py moderate_scan --digest
```

备份保留天数仍是 260 用户要的「永久」：

```
BACKUP_KEEP_DAYS 0
```

### 4. 备份和公网核对

```
已备份到 /app/backups/sjtu-ow-20261010-153634.tar.gz（210.9 MB）
异地备份没有开启。本地这份没有加密，……
```

```
/                                                            200
/news/                                                       200
/news/网站正式发布/                                           200   <title>网站正式发布 · SJTU-OW</title>
/teams/                                                      200
/teams/1/                                                    200   <title>测试战队 · 战队 · SJTU-OW</title>
/members/                                                    200
/accounts/login/                                             200
/accounts/password/reset/                                    200
/about/                                                      200
/me/                                                         302 → /accounts/login/?next=/me/
/admin/                                                      302 → /accounts/login/?next=/admin/
/healthz                                                     503   {"disk": {"ok": false}，其余 ok}
/sitemap.xml                                                 200
/robots.txt                                                  200
/favicon.ico                                                 301 → /static/img/favicon.303999ebf760.ico
首页响应头：content-security-policy（旧站那条，含 'inline-speculation-rules'）、strict-transport-security
```

### 5. 文档

- `docs/frontend-migration.md` 第 10 节：每件加「拍板」一栏
- `docs/design-next.md`：决定表加 D10–D13，变更记录加一行
- `docs/cutover.md`：第 4 节后面记这次回滚和学到的
- STATUS：文件头（正式站是旧站）、「你已经拍板的」32、「还没定的」只剩两件、「现在该谁动手」、轮次表
- AGENTS：重构一节改成「正式站在旧站」；新坑：新旧栈同一个 Compose 项目和服务名会占掉旧镜像的标签

## 设计偏差

无。

## 未完成 / 顺带发现 / 需要确认

- **需要确认**：定时任务现在是割接前的写法（按夏令时减 6 小时写死）。10-25 柏林换冬令时以后，北京时间晚一小时（凌晨 4 点备份），照样是深夜；要不要换成仓库模板里 `at-shanghai.sh` 的写法
- **需要确认**：磁盘剩 19%，`/healthz` 一直 503。本项目能清的是约 4 GB 构建缓存和新栈留下的几个镜像；清不清、清哪些要你点头（AGENTS「磁盘」那条）
- **需要确认**：异地备份（R2）还没配置（上线前就在等）
- **顺带发现**：259 起的新栈用 `sjtu-ow` 同一个项目名，旧站镜像的标签被占；下一次割接前要先给旧镜像另打一个标签（比如 `sjtu-ow-web:legacy`），写进了 `docs/cutover.md`
- **顺带发现**：停新栈时 Compose 报 `SIGNING_KEY`、`FIELD_ENCRYPTION_KEY`、`SMTP_*` 没设——这是这次停的命令没带 `--env-file`；新栈当初起的时候带没带（`deploy/upgrade.sh` 有 `.env` 就带），容器已删，没法再核实

## 改动文件

- 正式站：`/etc/cron.d/sjtu-ow`（换回割接前的）；容器换回旧站；`/root/rollback-check/`（脚本、日志、新栈最后的库、改前的 cron）
- 仓库：`docs/frontend-migration.md`、`docs/design-next.md`、`docs/cutover.md`、`handoff/STATUS.md`、`AGENTS.md`、本轮目录
