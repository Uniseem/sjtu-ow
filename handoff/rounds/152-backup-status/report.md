# 152 备份状态写下来，出问题时提醒站长（报告）

## 做了什么

1. `core/management/commands/backup.py`：
   - `STATUS_FILE`、`write_status()`、`read_status()`
   - `upload()` 返回结果；`handle()` 上传失败时先写 `failed` 再抛
2. `core/admin_todo.py`：`BACKUP_STALE`（36 小时）、`backup_problems()`；`_site_rows()` 每个问题一行（不带链接）
3. `core/templates/core/admin/todo_panel.html`：没有链接的行只显示文字
4. 设计 v6.45，README 备份一节
5. 测试：`core/tests/test_offsite_backup.py` 加 1 条、`core/tests/test_admin_functions.py` 加 1 条

## 命令输出

变异（测试机，8 处，第一次全部被抓到）：

```
baseline green, 2 tests
caught a failed upload leaves no status -> test_each_run_leaves_a_status
caught a good run leaves no status -> test_each_run_leaves_a_status
caught skipped reads as uploaded -> test_each_run_leaves_a_status
caught no word without backups -> test_the_owner_hears_about_missing_or_failed_backups
caught old backups look fine -> test_the_owner_hears_about_missing_or_failed_backups
caught fresh backups look stale -> test_the_owner_hears_about_missing_or_failed_backups
caught a failed upload is not mentioned -> test_the_owner_hears_about_missing_or_failed_backups
caught the panel drops rows without a link -> test_the_owner_hears_about_missing_or_failed_backups
restored and green; missed: none
```

整组检查（测试机）：

```
1581 条测试分成 4 片
分片 1：396 passed in 37.87s
分片 2：395 passed in 37.05s
分片 3：395 passed in 36.51s
分片 4：395 passed in 36.63s
== 迁移 (23:20:49)
No changes detected
== 生产配置 (23:20:50)
System check identified no issues (0 silenced).
== 错误页和模板一致 (23:20:51)
== Docker 镜像 (23:20:52)
构建成功：83560f0dc22a
== 全部通过 (23:20:52)
```

演示站：备份目录里有今天凌晨的一份，所以没有提醒（`backup_problems()` 返回空）；`last-backup.json` 要等今晚的备份跑过才会有：

```
-rw-r--r-- 1 root root 226053848 Oct  3 19:00 sjtu-ow-20261004-030004.tar.gz
[]
```

## 没做 / 未验证

- 演示站上没等到今晚那次备份写出状态文件
