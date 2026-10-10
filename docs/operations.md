# 机器与运维

连接测试机、读服务器状态、准备部署、备份或恢复前读本文件。这里是机器参数和操作说明；当前部署状态、待用户确认和期限只维护在 [STATUS](../handoff/STATUS.md)。部署到任何服务器仍需用户授权，新栈割接另外先读 [cutover.md](cutover.md) 第 5 节。

通用 Django 操作步骤见 [旧站使用与运行手册](legacy-guide.md)；新栈的设计规格见 [design-next.md](design-next.md) 和 [12-architecture.md](rewrite-research/12-architecture.md)。机器上的历史快照描述不当成当前探测结果。

## 测试机

**测试机是 `2a0e:6a80:3:9c7::`（只有 IPv6），各种测试检查都在这台上跑。** 用户 2026-10-04：「各种测试检查放到 IP 为 185.99.135.224 的 vps 上进行，你可以搭建完整的工作测试流」，随后「测试机换到 IP 为 2a0e:6a80:3:9c7:: 的 vps 上。这台机子所有资源都由你掌控，请务必用满性能以达最高效率」。

| 项目 | 内容 |
|---|---|
| 机器（128 核对） | Debian 13，4 核 AMD EPYC 9275F，19 GB 内存，Docker 已装；146 装了 `chromium`、`fonts-noto-cjk`（截图用）。出 IPv4（GitHub、PyPI）走 Cloudflare WARP（`warp-svc`）。还跑着 Komari 监控探针（`komari-agent`） |
| 权限 | **整台机器归本项目用**，资源随便用；`warp-svc` 和 `komari-agent` 别停（前者断了就连不上 GitHub） |
| 登录 | SSH 密钥。**本机没有 IPv6 时走用户的端口转发 `189.24.110.12:2222`**（2026-10-05 起，见下）。登录用户和密钥在开发者本机的 `~/.ssh/config`，**不写进仓库**（仓库是公开的）。`remote-check.sh` 默认连 SSH 别名 `sjtu-ow-test`；直连 IPv6 时 `CHECK_HOST=2a0e:6a80:3:9c7::`，`scp` 要给 IPv6 地址加方括号，脚本自己处理 |
| 检查目录 | `/srv/sjtu-ow-check/`：`uv/`（uv 二进制，从 GitHub 发布页下载、核对过 sha256，缓存也在这里）、`repo/`（从 GitHub 克隆，每次检查切到传过来的快照）、`shards/1…4`（pytest 分片用的 worktree，各有自己的 `.venv` 和测试库）、`runs/`（每次检查的脚本、日志、退出码，留最近 30 次）、`lock`。Docker 里留一个 `sjtu-ow:check` 镜像，每次构建后删掉上一个 |
| 怎么用 | 本机 `bash scripts/remote-check.sh`，见 [开发与验收](development.md)。整组检查（含 `docker build`）约 1 分半，pytest 分 4 片、每片 40 秒左右 |
| 以后要部署测试站 | 照 docs/legacy-guide.md「生产 / 测试环境启动」：部署目录 `/srv/sjtu-ow`、Compose 项目名 `sjtu-ow-test`、每条命令带 `--env-file .env`。要 HTTPS 得有一个解析到这个 IPv6 地址的域名 |

**连测试机走端口转发**（用户 2026-10-05：「测试机因为是 v6 连不上，所以我改用另一台机进行了端口转发。使用 189.24.110.12:2222 可进行 ssh 连接」）：开发者本机没有 IPv6，184–195 一直连不上测试机，检查都在本机跑。现在 `189.24.110.12` 的 2222 端口转到测试机的 22。`189.24.110.12` 是用户自己的机器（也是正式站域名的反向代理 `anylocate.cc`），**只有 2222 是转发，22 端口是那台机器自己的，别去连、别动**。本机 `~/.ssh/config` 这样配（用户和密钥照原来测试机那条）：

```
Host sjtu-ow-test
    HostName 189.24.110.12
    Port 2222
    User <登录用户>
    IdentityFile <密钥>
    HostKeyAlias 2a0e:6a80:3:9c7::
```

`HostKeyAlias` 让 SSH 用测试机原来的主机密钥核对（2026-10-05 核过，经转发拿到的 ED25519 指纹和直连 IPv6 时记下的一样：`SHA256:m6BeQ0v27W6tSBnKSM0kMmJ4FSFJyT4g1uUGUwecsO0`），转发那头要是换成了别的机器会报警。`bash scripts/remote-check.sh` 不用改参数；`scp` 拿截图写 `scp "sjtu-ow-test:/tmp/sjtu-ow-screens/out/*.png" 本机目录`。

**原来的测试机 `185.99.135.224`**（2026-09-18 起）重装过、没有 Docker，128 在上面搭过一次，换机器后把 `/srv/sjtu-ow-check` 删了，现在不用。上面有别人的东西（Komari 探针、`/opt` 和 `/root` 下的 Flutter、Android、FlClash 工具链），再上去也只动自己建的目录，不做全局清理。

### 第二台：169.58.217.180（用户 2026-10-03 指定，v6.0 起；**183 起是正式站**）

用户：「当前版本部署到 169.58.217.180 的 vps 上，端口使用 22887。不需要配置反代，我自己会配」。和测试机的区别：**本项目不占 80/443**，Caddy 只在 22887 上听 HTTP，域名和 HTTPS 由用户自己的反向代理负责。

| 项目 | 内容 |
|---|---|
| 登录 | `root`，SSH 密钥（开发者本机的 `id_ed25519`），Debian 12，Docker 29 / Compose v5 |
| 部署目录 | `/srv/sjtu-ow`；`.env` 权限 600，三把密钥在服务器上生成（`secrets.token_urlsafe`），没离开过服务器 |
| Compose | 项目名 `sjtu-ow`。**每条命令**：`docker compose -p sjtu-ow -f deploy/docker-compose.yml -f deploy/docker-compose.vps.yml --env-file .env` |
| 本机专用文件（不在仓库里） | `deploy/docker-compose.vps.yml`：`proxy` 的端口用 `!override` 换成 `22887:80`，站点地址 `:80`，挂 `Caddyfile.vps`；`deploy/Caddyfile.vps`：仓库 Caddyfile 的全局块（`admin off` 下面）加 `servers { trusted_proxies static private_ranges 100.96.0.0/12` 和 `trusted_proxies_strict }`（120 起），信任反代带来的 `X-Forwarded-Proto` 和访客 IP。另一个会话 2026-10-03 20:12（服务器时间）调过资源：`.env` 的 `GUNICORN_WORKERS=5`，`docker-compose.vps.yml` 给 `web` 加了 `cpu_shares: 2048`（CPU 争用时网站优先），改前的备份是同目录下的 `*.bak-202610032012` |
| 域名与反代（120 起） | `sjtu.ow-shanghaiuniversity.com` → CNAME `anylocate.cc`（`189.24.110.12`，用户自己的反向代理，**在另一台机器上**）→ 经 **Cloudflare WARP 内网**连到本机 22887，来源地址 `100.96.0.x`。所以 `Caddyfile.vps` 要信任 `100.96.0.0/12`，否则反代带来的 `X-Forwarded-Proto: https` 和访客 IP 会被 Caddy 丢掉 |
| `.env` 要点 | `DJANGO_ALLOWED_HOSTS=sjtu.ow-shanghaiuniversity.com,169.58.217.180,localhost`；`SITE_URL=https://sjtu.ow-shanghaiuniversity.com`；`DJANGO_CSRF_TRUSTED_ORIGINS=https://sjtu.ow-shanghaiuniversity.com,http://169.58.217.180:22887`（120 改，改前备份在服务器的 `/root/sjtu-ow-backups/`；备份里有密钥，别放在仓库目录里）。**域名不在 `ALLOWED_HOSTS` 里时，Django 生成的页面（后台、登录、成员个人页）全部 400，预渲染页照常**，看起来像「有些页面坏了」。改了 `SITE_URL` 要同步 Wagtail 站点地址（`content.services.sync_default_site_from_site_url()`）再全量 `prerender`。`DJANGO_SECURE_SSL_REDIRECT=false`（跳转由用户的反向代理做）；`TEST_ENVIRONMENT` 183 起删掉了（用户 10-04 说转正式站；删前的 `.env` 在 `/root/sjtu-ow-backups/env-before-golive-*`） |
| 定时任务 | `/etc/cron.d/sjtu-ow`（不碰 root 的 crontab）。服务器时区是 **Europe/Berlin**，cron 不支持 `CRON_TZ`。**218 起模板（`deploy/crontab.example`）每条是「每小时一次」，由 `deploy/at-shanghai.sh` 按北京时间判断，不再换算**。实际切换状态与期限只看 STATUS；操作见 docs/legacy-guide.md「把正式站的 cron 换成新写法」，要登录服务器改，得用户点头 |
| 登录后台 | 生产设置的 Cookie 只走 HTTPS，**直接用 `http://IP:22887` 登录不了**，要等反向代理配好 HTTPS。管理员账号由用户自己建：`… exec web python manage.py createsuperuser`。184 起它建的账号邮箱直接算已验证；183 后用户建的第一个超级管理员（`ow4sjtu@126.com`）当时卡在验证码页，是在服务器上手动标成已验证的。有人收不到验证码：`… exec web python manage.py verify_email 邮箱` |
| 正式站（183 起） | 用户 10-04：「现在这个站点，给他变成正式的吧。封面图片之类的保留」。演示数据（40 个 `demo.example.com` 账号、战队、文章、评论、赛事、内战）已清，**图片库原样保留**（478 张、64 个集合，含默认封面、默认头像和演示用的动漫头像「头像」集合；动漫头像版权归画师，出处记在图片说明里）。演示站的最终备份在 `/root/sjtu-ow-backups/demo-final-20261004-123749.tar.gz`，旧库改名留在数据卷 `/app/data/demo-final.sqlite3`。当初灌演示数据的脚本挪进了 `/root/demo-era-scripts/`，**别再对这台机器跑**。现在库里的是真实数据：**绝不用备份整库覆盖**，升级前想留底就先 `backup`。102–182 的演示站经过见 `handoff/rounds/102-demo-site/`、`183-go-live/` |

在服务器上跑一段脚本：`$C exec -T web python manage.py shell < /root/脚本.py`（`$C` 是上面那条 Compose 命令；Linux 上 Django 会把整段输入当脚本执行）。

**每轮升级**（120 起的做法，脚本在服务器 `/root/`，不在仓库里）：
1. 本机把改动的文件（`git status` 里除 `handoff/`、`docs/` 以外的）列成 `shipN.txt`、打成 `shipN.tar`，两个都传到 `/root/`
2. 跑 `sh /root/deploy_ship.sh N`：解包、去 CRLF、构建、迁移、重启、全量预渲染、健康检查。129 起它先检查 Compose 配置读不读得出来，读不出来就停
3. 提交推送以后跑 `sh /root/align_after_push.sh N`：**只把清单里的文件放回原样**，再 `git pull`

**服务器上有三样本机专用的未跟踪文件**：`deploy/docker-compose.vps.yml`、`deploy/Caddyfile.vps`、`.env.bak-*`，129 起写在服务器的 `.git/info/exclude` 里，`git status` 不再显示。**别按 `git status` 删未跟踪文件**：127 对齐时这样删，把 `docker-compose.vps.yml` 和它的备份一起删了（当时看的 `git status | head` 截掉了这两行），129 部署时构建、迁移、重启全失败（运行中的容器不受影响），照会话里读到过的内容恢复

**仓库的 `deploy/Caddyfile` 改了之后**，`Caddyfile.vps` 要跟着重新生成：它就是仓库那份在 `admin off` 下面插上一行说的 `servers` 块（105 用 `awk` 插入、`diff` 核对；120 起块里是两行：`trusted_proxies static private_ranges 100.96.0.0/12`、`trusted_proxies_strict`）；然后 `caddy validate`、`$C restart proxy`。升级后用 `docker images | grep sjtu-ow` 看一眼镜像时间：105 有一次 `build -q` 什么都没构建也没报错，容器跑的还是旧镜像

这台机器上还跑着 WordPress、HedgeDoc、FileCodeBox、相册和几个监控进程，规矩和测试机一样：只动 `/srv/sjtu-ow` 和 `sjtu-ow` 这个 Compose 项目，不做全局清理。**磁盘**（183、186）：158 GB 的盘上面还有别的服务，183 时只剩 19%，`/healthz` 的磁盘检查（剩余要大于 20%）报 503。大头是 Docker 构建缓存：本项目每次升级 `docker compose build` 留下约 200 MB（70 多次构建攒了 15.6 GB），另一个项目 4 GB。186 经用户同意跑了 `docker builder prune -af`（全局，清掉 19.8 GB），剩余回到 31%。以后升级多了还会涨，`docker buildx du` 看大小，再清要用户点头。升级照 docs/legacy-guide.md「生产 / 测试环境启动」，命令换成上面那条，升级后全量 `prerender`。
