# 054 部署修复：重启策略、健康检查、定时任务

## 背景

用户 2026-09-18：「继续完成网站」。053 第一次在测试机上部署，发现三个没修的问题。

## 任务

1. **重启策略**：`deploy/docker-compose.yml` 的 `web`、`worker`、`proxy` 都没写 `restart:`，服务器重启或进程崩溃后网站不会自己起来。三个都加 `restart: unless-stopped`
2. **容器健康检查**：现在请求 `http://127.0.0.1:8000/healthz`，被 `ALLOWED_HOSTS` 拒成 400。改成带上 `ALLOWED_HOSTS` 里的第一个域名作为 `Host`，并带 `X-Forwarded-Proto: https`（否则 `SECURE_SSL_REDIRECT` 会把它跳到 HTTPS）。逻辑放进一个脚本文件，不在 YAML 里写一长串引号
3. **定时任务**：`deploy/crontab.example` 的命令没带 `-p` 和 `--env-file`。正式站项目名是 `sjtu-ow`，照写能用；测试机项目名是 `sjtu-ow-test`，照写会找不到容器。改成顶部两个变量，按环境改
4. 在测试机上：拉最新代码、重建、验证容器变成 healthy；**用 `/etc/cron.d/` 下的独立文件装定时任务**，不碰 root 的 crontab（机器上还有别的项目）；跑一次全量预渲染

不做：

- 内战管理员没拿到内战权限：053 发现的第四个问题，查下来**是真的漏了权限**（不只是提示过时），单独一轮（055）
- web 和 worker 各构建一次镜像：不影响功能，以后再说

## 验收标准

1. 健康检查脚本有测试：请求带对了 `Host` 和 `X-Forwarded-Proto`；`/healthz` 返回 503 时脚本失败
2. 测试机上：三个容器 `restart` 策略生效；`web` 显示 healthy；**重启 Docker 服务之外的方式验证重启策略**——杀掉容器的主进程，看它自己起来
3. 定时任务装好后，手动触发其中一条，确认命令本身能跑
4. 其他项目的容器不受影响
5. 本地四项检查干净，推送后 CI 绿
