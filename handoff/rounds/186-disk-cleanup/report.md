# 186 正式站服务器清理磁盘（报告）

用户同意后在 169.58.217.180 上执行：

```
before: free 19.2% (30.4G)
Reclaimable:	19.77GB
Total:		19.77GB
Total:	19.77GB
Reclaimable:	0B
Total:		0B
after: free 31.2% (49.4G)
```

只清了构建缓存（`docker builder prune -af`），镜像、容器、卷都没动。之后：

```
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"}, "disk": {"ok": true, "detail": "free space 31.2%"}, "worker_heartbeat": {"ok": true, "detail": "ok (29s ago)", "affects_status": true}, "task_backlog": {"ok": true, "detail": "ok", "affects_status": true}}}
sjtu-ow-proxy-1 Up About an hour
sjtu-ow-web-1 Up 20 minutes (healthy)
sjtu-ow-worker-1 Up 20 minutes
other containers: 14 running, unhealthy: 0
```

公网 `https://sjtu.ow-shanghaiuniversity.com/healthz` 也是 `"status": "ok"`。

影响：下次升级构建镜像时要重新下载基础镜像、重装依赖（缓存没了），会比平时慢几分钟；另一个项目下次构建也一样。

## 没做

- 没有让升级脚本自动清缓存：那也是全局清理。本项目每次构建约攒 200 MB（缓存里本项目的 `COPY . .` 有 76 条，合计 15.6 GB），按现在的升级频率一两个月又会涨回来，到时 `docker buildx du` 看一眼、再请用户点头
