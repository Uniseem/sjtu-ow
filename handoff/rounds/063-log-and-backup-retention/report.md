# 063 实现报告

## 结论

**完成。** 三个容器加了日志轮转（每个最多 5 个 10MB），测试机上已生效；异地备份每次上传成功后清理超过 14 天的本站备份。核对访问日志时发现设计和隐私政策草稿都写得不对，一并改成实际情况。

**部署时发现一个更大的问题，留给 064**：worker 容器没有挂载静态文件卷，**所有由事件触发的页面重新生成在服务器上都失败了**（见文末）。

## 1. 日志轮转

`deploy/docker-compose.yml` 加一个 `x-logging` 锚点，`web`、`worker`、`proxy` 都引用：`json-file` 驱动，`max-size: 10m`、`max-file: 5`。

Docker 自带的驱动只能按大小轮转，设计 15.5 原来写的「保留 14 天」做不到，改成按大小，写明保留多久取决于访问量。

## 2. 访问日志到底记了什么（顺带核对出来的）

设计 15.5 原来写「访问日志：Caddy 记录的请求：时间、IP、路径……14 天」；060 的隐私政策草稿写「不单独记录和保存访问日志」。**两个都不对**：

- `deploy/Caddyfile` 里没有 `log` 指令，Caddy 不记访问日志
- 但 `entrypoint-web.sh` 里 gunicorn 开着 `--access-logfile -`，每个请求一行

在测试机上发一个请求看实际记下的内容：

```
$ curl -s -o /dev/null -w "%{http_code}\n" "https://sjtu.ow-shanghaiuniversity.com/accounts/login/?probe=063"
200
$ docker logs --since 2m sjtu-ow-test-web-1 2>&1 | grep probe=063
172.19.0.3 - - [18/Sep/2026:18:22:27 +0800] "GET /accounts/login/?probe=063 HTTP/1.1" 200 5844 "-" "curl/8.17.0"
```

来源是 Caddy 的内网地址 `172.19.0.3`，**不是用户 IP**；有路径（含查询参数）、状态码、浏览器标识。应用代码里唯一碰 IP 的是 `core/ratelimit.py`，只拿来当缓存键，不写日志。

改动：

- 设计 15.5 访问日志一行按实际写；表下加「访问日志和应用日志都不记录用户 IP，以后要记先改隐私政策」
- 隐私政策草稿改成「服务器会记录每次访问的时间、访问的页面地址和浏览器类型，用于排查故障，**不记录你的 IP 地址**；这些记录写满一定大小后自动覆盖，不长期保存」
- 新测试 `test_no_log_records_the_visitor_ip`：Caddyfile 没有 `log` 指令，gunicorn 没有 `--forwarded-allow-ips`、`--access-logformat`。任何一条变了都可能开始记 IP，测试会红，提醒先改政策

## 3. 异地备份的保留期

`core/offsite.py` 新增 `prune(keep_days)`，`backup` 命令在上传成功后调用，天数和本地同一个（`--keep-days`，默认 `BACKUP_KEEP_DAYS` = 14）。

- **只删本站的备份**：文件名要符合 `sjtu-ow-年月日-时分秒.tar.gz.enc`，**而且**要直接放在设置的前缀下（`config.key_for(文件名) == 键`）。第二条是写测试时想到的：按前缀 `sjtu-ow` 列表，S3 也会返回桶根目录下的 `sjtu-ow-….enc` 和子目录里的文件，第一版只看文件名会把它们删掉
- 分页读取（`IsTruncated` / `NextContinuationToken`），每次最多删 1000 个（`delete_objects` 的上限）
- 清理失败只打印警告，命令照常成功：旧文件多留一天不会丢数据；上传失败仍然让命令失败（031 的规则不变）

隐私政策草稿「异地备份：保留【天数】」填为 14 天。设计 16.7 第 3 步、附录 C 参数表同步。README 写明 R2 的 API 令牌要有删除权限。

## 测试

`core/tests/test_offsite_prune.py` 6 条：旧的删、新的留；不是本站的不动（7 种键：别的文件、未加密、别的前缀名、没有时间戳、前缀外、桶根目录、子目录）；分页每页 2 个共 5 个全部读到；1001 个分两批删（1000 + 1）；`backup` 命令上传后清理并打印；清理失败只警告。

`core/tests/test_healthcheck_script.py` 加 4 条：三个服务各一条日志轮转，一条不记 IP。

## 变异

```
KILLED   只看文件名，不核对前缀位置  | 1 failed, 1 passed in 0.16s
KILLED   不核对文件名  | 1 failed, 1 passed in 0.16s
KILLED   不看时间  | 1 failed in 0.16s
KILLED   只读第一页  | 1 failed, 2 passed in 0.16s
KILLED   一次删超过 1000 个  | 1 failed, 3 passed in 0.17s
KILLED   上传后不清理  | 1 failed, 4 passed in 0.21s
KILLED   清理失败让备份失败  | 1 failed, 5 passed in 0.22s
KILLED   去掉日志轮转（第一处）  | 1 failed, 25 passed in 0.54s
KILLED   改大单个日志文件  | 1 failed, 25 passed in 0.51s
```

不记 IP 的测试另外两处变异（Caddyfile 加一行 `log`；gunicorn 加 `--forwarded-allow-ips "*"`）：

```
1 failed, 13 deselected in 0.05s
1 failed, 13 deselected in 0.04s
```

11/11 被抓到，全部还原。

## 测试机

先用本轮的改动打补丁部署（提交后再把服务器上的仓库对齐到提交）。设计 16.8：先备份再更新；本轮没有迁移。

```
--- 1. 升级前备份:
已备份到 /app/backups/sjtu-ow-20260918-182711.tar.gz（0.1 MB）
--- 2. 构建:
 Image sjtu-ow-test-web Built
 Image sjtu-ow-test-worker Built
--- 3. 启动:
web: healthy
--- 4. 日志配置:
web: {json-file map[max-file:5 max-size:10m]}
worker: {json-file map[max-file:5 max-size:10m]}
proxy: {json-file map[max-file:5 max-size:10m]}
--- 5. 其他容器:
<其他项目> Up 7 days
<其他项目> Up 7 days
<其他项目> Up 8 days (healthy)
<其他项目> Up 8 days (healthy)
```

```
$ curl -sI http://sjtu.ow-shanghaiuniversity.com/
HTTP/1.1 308 Permanent Redirect
Location: https://sjtu.ow-shanghaiuniversity.com/
$ curl https://sjtu.ow-shanghaiuniversity.com/healthz
{"status": "ok", ... "disk": {"ok": true, "detail": "free space 77.5%"}, "worker_heartbeat": {"ok": true, "detail": "ok (6s ago)", ...}}
```

异地备份在测试机上没开，**`prune` 没有对真实的 R2 跑过**，未验证。等 R2 凭据到位后跑一次 `backup`，看输出里有没有「异地旧备份没清理掉」。

测试机上没有任何管理员账号（`superusers 0 staff 0`），协议页面的修订全部是命令写的，所以用 `load_legal_pages --force` 把改过的隐私政策发布上去：

```
已发布「用户协议」
已发布「隐私政策」
```

## 发现的问题：worker 生成的页面在服务器上全部失败（→ 064）

发布后预渲染的静态页 25 秒后还是旧文字，走 Django 的版本（带查询参数）已经是新的：

```
$ curl -s https://sjtu.ow-shanghaiuniversity.com/privacy/ | grep -o ...
不单独记录和保存访问日志
异地备份：保留【天数，建议与本地备份一致】
$ curl -s "https://sjtu.ow-shanghaiuniversity.com/privacy/?x=1" | grep -o ...
不记录你的 IP 地址
异地备份：保留 14 天
```

worker 日志：

```
/app/.venv/lib/python3.13/site-packages/django/core/handlers/base.py:62: UserWarning: No directory at: /app/staticfiles/
预渲染失败 /terms/：渲染出错：Missing staticfiles manifest entry for 'css/error.css'
预渲染失败 /privacy/：渲染出错：Missing staticfiles manifest entry for 'css/error.css'
```

`deploy/docker-compose.yml` 里 `worker` 没挂 `static` 卷，读不到 `collectstatic` 生成的清单，渲染任何引用静态文件的模板都出错。任务本身记为成功（失败被捕获后只写日志），`/healthz` 也看不出来。

**影响**：设计 13.13.4 事件表的 14 行在服务器上全部不生效——发布文章、改赛事、报名、改昵称之后，静态页都停在旧版本，直到有人在 `web` 里跑全量生成。053 起的「全量预渲染已跑」都是在 `web` 容器里跑的，所以一直没暴露；056、057 报告里的「测试机已生效」指的是代码部署了，**没有在测试机上看过事件触发的生成结果**。

不在本轮修（不扩大范围），064 第一件做。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
236 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python -m pytest -q
839 passed in 53.64s
```

829 → 839。

## 顺带看到的（不在本仓库）

测试机上另一个项目的一个容器日志目录有 1.4G（同样没设轮转）。不是本项目的，没动，只在对话里告诉用户。

## 改动文件

```
deploy/docker-compose.yml                日志轮转
core/offsite.py                          prune、_is_ours、_all_objects
core/management/commands/backup.py       上传后清理
core/tests/test_offsite_prune.py         新建，6 条
core/tests/test_healthcheck_script.py    日志轮转 3 条、不记 IP 1 条
content/legal/privacy.md                 日志说法、异地保留 14 天
docs/design.md                           15.5、16.7、附录 C、附录 D（v1.5.14）
README.md                                日志、异地清理
handoff/STATUS.md
handoff/rounds/063-log-and-backup-retention/
```
