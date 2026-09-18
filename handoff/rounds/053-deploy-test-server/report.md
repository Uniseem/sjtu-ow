# 053 实现报告

## 结论

**部分完成，用户叫停收尾。** 测试环境已经在测试机上跑起来了：`https://sjtu.ow-shanghaiuniversity.com` 能打开，证书是 Let's Encrypt 签的，HTTP 自动跳转 HTTPS，测试环境横幅和禁止抓取都生效，`/healthz` 四项全绿。**机器上其他项目的容器没受影响。**

部署中发现 **4 个问题**：README 的部署命令写错了（已改）；重启策略缺失、容器健康检查必然失败、`init_site` 的一句过时提示（**这三个还没修**）。

没做：全量预渲染、创建超级管理员（留给用户）。

## 过程

### 1. 代码和 `.env`

从公开仓库 clone 到 `/srv/sjtu-ow`（`19264ec`）。`.env` 在服务器上生成，三把密钥用 `openssl rand -base64 48` 直接写进文件，**没有打印出来，也没经过开发机**：

```
-rw------- 1 root root 838 Sep 18 05:27 .env
DJANGO_SECRET_KEY 64 字符
FIELD_ENCRYPTION_KEY 64 字符
BACKUP_ENCRYPTION_KEY 64 字符
```

`TEST_ENVIRONMENT=1`，`CADDY_SITE_ADDRESS=sjtu.ow-shanghaiuniversity.com`。

### 2. 问题一：README 的部署命令会让 Caddy 用 localhost（已改）

```
--- 不加 --env-file（README 现在的写法）:
      CADDY_SITE_ADDRESS: localhost
--- 加 --env-file .env:
      CADDY_SITE_ADDRESS: sjtu.ow-shanghaiuniversity.com
```

Compose 替换 `${CADDY_SITE_ADDRESS}` 时，默认去 `deploy/`（Compose 文件所在目录）找 `.env`，不是仓库根目录。照 README 原来的写法部署，Caddy 只服务 `localhost`，**不会申请证书**。

连带发现：容器的环境变量固定读 `../.env`（`env_file`），而 README 原来给测试环境的例子是 `--env-file .env.test`——那样 Caddy 用 `.env.test`，容器却用 `.env`，两边对不上。**一份代码目录只能跑一套环境。**

README 已改成实际走通的步骤。

### 3. 构建、迁移、启动

构建 52 秒。**先迁移再启动**（README 原来是先 `up` 再 `exec migrate`，worker 一启动就要读任务表）：

```
  Applying wagtailusers.0015_userprofile_keyboard_shortcuts... OK
已按 SITE_URL 设置站点：sjtu.ow-shanghaiuniversity.com:443
...
以下内容仍等到后续里程碑写入（命令可重复执行）：
  - 内战管理员的内战管理权限（M6）
```

### 4. 证书

Caddy 日志：

```
"msg":"trying to solve challenge","identifier":"sjtu.ow-shanghaiuniversity.com","challenge_type":"http-01"
"msg":"served key authentication" ... "remote":"23.178.112.103:43693"
"msg":"served key authentication" ... "remote":"13.60.199.85:61024"
"msg":"served key authentication" ... "remote":"3.145.35.41:21492"
"msg":"served key authentication" ... "remote":"35.166.244.149:29764"
"msg":"certificate obtained successfully","identifier":"sjtu.ow-shanghaiuniversity.com"
```

HTTP-01 验证，Let's Encrypt 从 4 个不同地方来访问，都拿到了验证文件。

### 5. 验证

从开发机访问（`--resolve` 绕开开发机被代理接管的 DNS）：

```
--- http 跳转:
308 -> https://sjtu.ow-shanghaiuniversity.com/
--- https 首页:
200 0
测试环境：这里不是正式网站，数据随时可能被清空
--- 证书:
subject= /CN=sjtu.ow-shanghaiuniversity.com
issuer= /C=US/O=Let's Encrypt/CN=YE2
notAfter=Dec 17 04:31:23 2026 GMT
--- robots:
User-agent: *
Disallow: /
--- healthz:
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"}, "disk": {"ok": true, "detail": "free space 79.4%"}, "worker_heartbeat": {"ok": true, "detail": "ok (0s ago)", "affects_status": true}, "task_backlog": {"ok": true, "detail": "ok", "affects_status": true}}}
200
```

`ssl_verify_result` 为 0，证书链校验通过。

**其他项目没受影响**，部署前后对比：

```
部署前：另一个项目的 4 个容器，均已运行 7 天，其中 2 个 healthy
部署后：同样 4 个容器，均已运行 7 天，其中 2 个 healthy（没有重启过）
```

（容器名隐去：仓库是公开的，`AGENTS.md` 规定不写机器上其他项目的名字。）

## 还没修的问题

### 问题二：没有重启策略

`deploy/docker-compose.yml` 里 `web`、`worker`、`proxy` 都没写 `restart:`。**服务器重启或进程崩溃后，网站不会自己起来。** 设计 15.4 要求单台服务器、允许计划内短暂停机，但不包括「重启后一直停着」。修法是三个服务都加 `restart: unless-stopped`。

### 问题三：容器健康检查必然失败

```
urllib.error.HTTPError: HTTP Error 400: Bad Request
starting 失败次数=2
```

健康检查请求的是 `http://127.0.0.1:8000/healthz`，生产配置里 `ALLOWED_HOSTS` 只有域名，请求被拒成 400。就算放行了主机名，`SECURE_SSL_REDIRECT` 还会把它跳到 HTTPS。容器会被标记为「不健康」。**网站本身不受影响**（Caddy 不依赖这个状态，外部访问 `/healthz` 是 200），但会误导排查，也让以后用 `condition: service_healthy` 的写法不可用。

### 问题四：`init_site` 说内战管理员权限「等到 M6」

M6 早就完成了。要么是这句提示过时了，要么内战管理员组真的没拿到权限。**没查**。

### 顺带：web 和 worker 各构建了一次镜像

两个服务的构建配置一样，却各自构建出一个镜像（`sjtu-ow-test-web`、`sjtu-ow-test-worker`）。可以让 worker 直接用 web 的镜像，省一半构建时间和磁盘。不急。

## 验收输出

本轮改的只有文档（`README.md`、`AGENTS.md`、`.env.example`），没改代码，不重跑 pytest。

```
$ ruff check . && ruff format --check .
All checks passed!
213 files already formatted
```

## 改动文件

```
README.md            部署步骤改成实际走通的；删掉「赛事/内战权限在后续里程碑写入」的过时说法
AGENTS.md            测试机一节补 Compose 项目名和 --env-file
.env.example         补 BACKUP_ENCRYPTION_KEY
handoff/STATUS.md
handoff/rounds/053-deploy-test-server/
```
