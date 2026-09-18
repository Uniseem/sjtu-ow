# 054 实现报告

## 结论

**完成。** 053 部署时发现的三个问题都修了，并在测试机上实测：

- 三个服务都有了重启策略，**杀掉 Caddy 主进程后它自己起来了**
- `web` 容器的健康检查从必然失败变成 **healthy**
- 测试机装上了定时任务，**cron 按时跑了一条，任务被 worker 执行成功**；顺便跑完了 053 没跑的全量预渲染

又发现两件事：Debian 12 默认**没装 cron**，装上的 cron **不支持 `CRON_TZ`**。

## 1. 重启策略

`deploy/docker-compose.yml` 的 `web`、`worker`、`proxy` 都加 `restart: unless-stopped`。

测试机上：

```
web restart=unless-stopped
worker restart=unless-stopped
proxy restart=unless-stopped
```

**模拟崩溃**：不能用 `docker stop` / `docker kill`，Docker 把那当成手动停止，不会自动重启。直接从宿主机杀容器的主进程：

```
杀掉前：Caddy 主进程 pid=1690649，重启次数=0
杀掉后：状态=running 重启次数=1 新 pid=1692158 启动于=2026-09-18T08:15:53.536511417Z
网站：200
```

选 Caddy 是因为它不写数据库；worker 和 web 会写 SQLite，没必要拿它们冒险。三个服务的策略是一样的。

## 2. 健康检查

新脚本 `deploy/healthcheck.py`：像 Caddy 一样，带上 `DJANGO_ALLOWED_HOSTS` 里的第一个域名作 `Host`、带 `X-Forwarded-Proto: https`，去请求 `/healthz`。Compose 里改成 `["CMD", "python", "/app/deploy/healthcheck.py"]`。

测试（`core/tests/test_healthcheck_script.py`）用生产那样的设置（只允许站点域名、`SECURE_SSL_REDIRECT` 打开）：

- 旧的写法（不带请求头）→ 400
- 脚本拼出来的请求 → 200
- 只带 `Host`、不带 `X-Forwarded-Proto` → 301
- `/healthz` 返回 503 时脚本退出码 1；200 时 0
- Compose 文件里三个服务都有 `restart: unless-stopped`，`web` 的健康检查用的是这个脚本

变异：

```
✓ 被抓到 不带 Host | 1 failed, 9 passed in 0.18s ['test_the_scripts_request_reaches_healthz']
✓ 被抓到 不带 X-Forwarded-Proto | 1 failed, 9 passed in 0.19s ['test_the_scripts_request_reaches_healthz']
已还原: True
```

测试机上：

```
health=healthy 失败次数=0 启动于=2026-09-18T08:14:18.21933767Z
2026-09-18 08:14:23.411975025 +0000 UTC exit=1
2026-09-18 08:14:28.786554804 +0000 UTC exit=1
2026-09-18 08:14:34.540299171 +0000 UTC exit=1
2026-09-18 08:14:38.219506692 +0000 UTC exit=1
2026-09-18 08:15:08.588327789 +0000 UTC exit=0

[2026-09-18 08:14:42 +0000] [1] [INFO] Listening at: http://0.0.0.0:8000 (1)
```

前四次失败是 gunicorn 还没起来：启动脚本先跑 `createcachetable` 和 `collectstatic`，**容器启动 24 秒后 gunicorn 才开始监听**，而原来的启动宽限期是 20 秒。宽限期改成 60 秒，以后静态文件多了也够。

## 3. 定时任务

### 模板

`deploy/crontab.example` 原来是 `docker compose -f $COMPOSE exec ...`，没带 `-p` 和 `--env-file`。正式站项目名 `sjtu-ow` 照写能用，**测试环境 `sjtu-ow-test` 照写会找不到容器**。改成顶部一个变量：

```
DC=docker compose -p sjtu-ow -f /srv/sjtu-ow/deploy/docker-compose.yml --env-file /srv/sjtu-ow/.env
```

每条命令写 `$DC exec -T web ...`，换环境只改这一行。

### 测试机上的两个意外

```
Time zone: Etc/UTC (UTC, +0000)
inactive
cron <none>
bash: line 1: crontab: command not found
```

**Debian 12 默认没装 cron。** 装上之后：

```
active
cron 3.0pl1-162
```

它的程序文件里搜不到 `CRON_TZ`，**不支持**。设计 16.5 的时间都是北京时间，模板里靠 `CRON_TZ=Asia/Shanghai` 声明，在这里不生效。所以测试机上的文件把时间换算成 UTC（北京时间减 8 小时，周日 04:30 变成 UTC 周六 20:30）。

### 装法

写成独立文件 `/etc/cron.d/sjtu-ow-test`，**不碰 root 的 crontab**（机器上还有别的项目）。这种文件比 crontab 多一列用户名；输出追加到 `/var/log/sjtu-ow-test-cron.log`。

用和 cron 一样的精简环境（`env -i`）手动跑了其中一条，全量预渲染：

```
全量生成完成：成功 9，失败 0，删除 0；目录占用 78 KB
```

**cron 按时执行**：

```
Sep 18 08:20:01 exc955slyd CRON[1695673]: (root) CMD ($DC exec -T web python manage.py shell -c "from integrations.tasks import deliver_due_webhooks; deliver_due_webhooks.enqueue()" >> $LOG 2>&1)
```

任务被 worker 执行了：

```
deliver_due_webhooks SUCCESSFUL 08:20:03
```

## 其他项目

```
（另一个项目）	Up 7 days
（另一个项目）	Up 7 days (healthy)
（另一个项目）	Up 7 days (healthy)
（另一个项目）	Up 7 days
sjtu-ow-test-proxy-1	Up 2 minutes
sjtu-ow-test-web-1	Up 3 minutes (healthy)
sjtu-ow-test-worker-1	Up 3 minutes
```

（容器名已隐去。）没受影响。

## 怎么把改动送到测试机的

一轮一个提交，所以先把 `deploy/` 下的改动做成补丁 `git apply` 到测试机上验证，验证完再提交推送，然后测试机上撤掉补丁、`git pull` 回到和仓库一致的状态。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
215 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python -m pytest -q
690 passed in 47.62s
```

680 → 690。推送后的 CI 结果记在下一轮。

## 改动文件

```
deploy/healthcheck.py                    新建
deploy/docker-compose.yml                重启策略；健康检查；宽限期 60 秒
deploy/crontab.example                   DC 变量；说明 Debian 不支持 CRON_TZ
core/tests/test_healthcheck_script.py    新建，10 条
README.md                                重启策略、健康检查、定时任务的说明
handoff/STATUS.md
handoff/rounds/054-deploy-fixes/
```

服务器上（不在仓库里）：装了 `cron` 包；新建 `/etc/cron.d/sjtu-ow-test`。
