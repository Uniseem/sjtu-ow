# 100 部署到 169.58.217.180（报告）

## 要求

用户 2026-10-03：「速度合并！然后当前版本部署到 169.58.217.180 的 vps 上，端口使用 22887.不需要配置反代，我自己会配」。合并见 099；这一轮是部署。

## 做了什么

1. **看机器**（只读）：`root` 用本机密钥能登；Debian 12、Docker 29.7.2、Compose v5.5.0、4 核 7.8G；已有 WordPress（58888）、FileCodeBox（40157）、相册（8188）、HedgeDoc（9005）和几个监控进程；80、443、22887 都没人用；`/srv` 是空的；时区 Europe/Berlin；装了 cron
2. **代码**：`git clone` 到 `/srv/sjtu-ow`，`a95a696`（099）
3. **本机专用文件**（不进仓库，理由：只有这台机器这样用）：
   - `deploy/docker-compose.vps.yml`：`proxy` 的 `ports: !override` 成 `"22887:80"`、`CADDY_SITE_ADDRESS: ":80"`、`volumes: !override` 换成挂 `Caddyfile.vps`。`docker compose config` 确认合并后只发布 22887
   - `deploy/Caddyfile.vps`：仓库 Caddyfile 的全局块加 `servers { trusted_proxies static private_ranges }`，同机（私有地址）反向代理带来的 `X-Forwarded-Proto: https` 会传给 Django
   - `.env`：脚本在服务器上用 `secrets.token_urlsafe` 生成三把密钥，没有打印、没有离开服务器，权限 600；主机和地址先用 IP；`TEST_ENVIRONMENT=1`；`DJANGO_SECURE_SSL_REDIRECT=false`
4. **启动**（照 README「生产 / 测试环境启动」，命令带两个 `-f`）：`build` → `migrate` → `createcachetable` → `init_site` → `up -d` → `prerender`
5. **定时任务**：`/etc/cron.d/sjtu-ow`，从 `deploy/crontab.example` 改：命令带两个 `-f`，北京时间按柏林夏令时减 6 小时，周日的那条挪到周六
6. **文档**：`AGENTS.md`「第二台」一节，`handoff/STATUS.md`

## 输出

```
SERVICE   STATUS                    PORTS
proxy     Up 20 seconds             443/tcp, 2019/tcp, 443/udp, 0.0.0.0:22887->80/tcp, [::]:22887->80/tcp
web       Up 20 seconds (healthy)   8000/tcp
worker    Up 20 seconds             8000/tcp
```

```
全量生成完成：成功 9，失败 0，删除 0；目录占用 165 KB
```

从本机访问：

```
/              200 text/html; charset=utf-8 14981B
/healthz       200 application/json 276B
/robots.txt    200 text/plain; charset=utf-8 26B
/members/      200 text/html; charset=utf-8 13272B
/tournaments/  200 text/html; charset=utf-8 12964B
```

```
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"}, "disk": {"ok": true, "detail": "free space 74.3%"}, "worker_heartbeat": {"ok": true, "detail": "ok (22s ago)", "affects_status": true}, "task_backlog": {"ok": true, "detail": "ok", "affects_status": true}}}
```

样式表 `/static/css/app.6c410012e410.css` 200、`immutable`；无头 Edge 截了首页，新风格和测试环境横幅都在。

## 未完成 / 需要用户

- 反向代理（用户自己配），要带 `X-Forwarded-Proto: https`
- 域名：要加进 `DJANGO_ALLOWED_HOSTS`、`SITE_URL`、`DJANGO_CSRF_TRUSTED_ORIGINS`，然后 `up -d`
- 管理员账号：HTTPS 好了以后用户自己 `createsuperuser`（Cookie 只走 HTTPS，直接用 IP 登录不了）；我不替人设密码
- `TEST_ENVIRONMENT=1` 是不是要关，等用户说
- **未验证**：worker 的事件触发生成（站里还没有内容可改）；定时任务还没到第一次运行时间
