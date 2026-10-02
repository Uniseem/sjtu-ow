# 103 `restore` 在 Docker 部署里恢复不了上传文件（报告）

## 做了什么

1. **`core/management/commands/restore.py`**：新函数 `empty_folder(folder)`，删掉目录里的每一项、保留目录本身（目录不存在就什么都不做，和原来清 `prerendered` 的行为一样）。恢复 media 改成 `empty_folder(media)` 再 `shutil.copytree(staged_media, media, dirs_exist_ok=True)`；清 `prerendered` 也用它
2. **测试**（`core/tests/test_ops_commands.py`，2 条）：
   - `test_restore_brings_the_uploads_back_and_drops_the_rest`：备份后删一个文件、加两个，恢复后 media 正好是备份里的样子
   - `test_restore_works_when_media_is_a_mounted_volume`：把 `os.rmdir` 换成对 media 和 prerendered 这两个目录本身报 `EBUSY`（子目录照常删，`shutil.rmtree` 在 Linux 上删子项时带 `dir_fd`，删顶层目录时不带），恢复要打印「恢复完成」、文件回来、静态页面清掉
3. **`AGENTS.md`**：那条坑改成「挂载的数据卷只能清空、不能删（102 发现，103 修了）」，提醒以后碰这两个目录的代码也一样
4. **服务器 169.58.217.180**：传上改过的文件、重建镜像、`up -d`、全量生成。另外用新镜像加三个**临时数据卷**真跑了一次恢复（和线上一样是挂载点，但不碰演示站正在用的卷），跑完删掉临时卷

## 命令输出

变异（`handoff/rounds/103-restore-media/mutate.py`，5 处）：

```
baseline green, 3 tests
caught media is removed and copied again (the old way) -> test_restore_works_when_media_is_a_mounted_volume
caught copying refuses an existing folder -> test_restore_works_when_media_is_a_mounted_volume
caught copying refuses an existing folder -> test_restore_brings_the_uploads_back_and_drops_the_rest
caught media is not emptied first -> test_restore_brings_the_uploads_back_and_drops_the_rest
caught emptying removes the folder itself -> test_restore_works_when_media_is_a_mounted_volume
caught the static pages are left -> test_restore_works_when_media_is_a_mounted_volume
caught the static pages are left -> test_restore_replaces_the_database_and_clears_prerendered
restored and green; missed: none
```

整组检查（开发服务器停着）：

```
All checks passed!
268 files already formatted
No changes detected
System check identified no issues (0 silenced).
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1231 passed in 234.91s (0:03:54)
```

服务器重建、重启：

```
 M core/management/commands/restore.py
?? deploy/Caddyfile.vps
?? deploy/docker-compose.vps.yml
 Image sjtu-ow-worker Built 
 Container sjtu-ow-worker-1 Starting 
 Container sjtu-ow-worker-1 Started 
proxy Up 3 hours
web Up 15 seconds (health: starting)
worker Up 15 seconds
```

在真的 Docker 数据卷上恢复 102 的演示备份（`rt103_data`、`rt103_media`、`rt103_pre` 三个临时卷，`prerendered` 里先放一个旧页面）：

```
  - 恢复 media 到 /app/media
  - 清空 /app/prerendered
恢复完成。
接下来（设计 16.7）：启动 web 和 worker，在后台触发全量重新生成，检查 /healthz 和关键页面。
media files: 1625
prerendered entries: 0
-rw-r--r-- 1 root root 2277376 Oct  2 23:56 db.sqlite3
rt103_data
rt103_media
rt103_pre
```

（最后三行是 `docker volume rm` 删掉的临时卷。102 同一份备份在旧代码下报 `Device or resource busy`、media 里 0 个文件。）

这条命令往临时卷里放旧页面那一步用了 `alpine` 镜像，服务器上原来没有，被拉了下来（标记时间 `23:56:25`，比当时早 21 秒），没有容器在用，删掉了：

```
Untagged: alpine:latest
Deleted: sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6
removed
```

升级后：

```
web Up About a minute (healthy)
worker Up About a minute
全量生成完成：成功 46，失败 0，删除 0；目录占用 1553 KB
```

首页、成员、资讯、赛事、内战都是 200，`/healthz`：

```
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"}, "disk": {"ok": true, "detail": "free space 73.8%"}, "worker_heartbeat": {"ok": true, "detail": "ok (25s ago)", "affects_status": true}, "task_backlog": {"ok": true, "detail": "ok", "affects_status": true}}}
```

## 发现的问题（不在本轮修）

- 恢复是先换数据库、再动 media。万一 media 这步因为别的原因失败（比如磁盘满），还是会停在「库新文件旧」的半截状态。更稳的顺序是先把 media 放好再换库，或者失败时提示怎么手工补；现在没有改，因为数据卷这个必然失败的原因已经没了
- 测试机 185.99.135.224 上的 `restore` 也是旧代码，那台还等着升级（STATUS 里原有的事项）

## 未验证

- 在 185.99.135.224 上恢复（没有那台机器的访问）
- 从对象存储（`--from-s3`）恢复：走的是同一段代码，这次只验证了本地备份文件
