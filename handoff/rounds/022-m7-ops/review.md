# 022 复核结果

> 实现方自查（用户外出）。等用户回来，008–022 可以一起交给 Grok 做独立复核。

## 结论

**通过，但 M7 没有完成。** 四条运维命令做完并做了真实的备份恢复演练，自查中修掉 **2 个会让备份/恢复真的失效的问题**，另外补了一条安全防线（`.gitignore`）。

**备份加密和异地同步没做**（设计 16.7 第 3 步），这是上线前必须补的。M7 剩下的大部分要在真实服务器上做，或者等用户拍板。

## 验证记录

| 验证 | 方法 | 结果 |
|---|---|---|
| 检查与测试 | `ruff`、`pytest`、`makemigrations --check`、生产 `check --deploy` | 511 passed，部署检查干净 |
| **完整演练** | 造数据 → 备份 → 删数据 → 恢复 → 验证 | 数据全部回来 |
| 加密字段 | 恢复后读 API Secret | 和创建时打印的**逐字符一致** |
| 在线备份 | 边写入边备份，检查快照 | `PRAGMA integrity_check` = ok |
| 密钥不一致 | 换一个 `FIELD_ENCRYPTION_KEY` | 动文件之前就拒绝，并点名字段 |
| 演练模式 | 不加 `--yes` | 什么都没改 |
| prerendered | 恢复后 | 目录清空、记录表清空 |
| 备份内容 | `tar tzf` | 只有 db 和 media，无 static / prerendered / `.env` |
| 保留期 | 造 20 天前和 3 天前的假备份 | 删旧留新，不碰非备份文件 |
| `cleanup_static` | 当前版本 / 40 天前 / 5 天前三个文件 | 只删 40 天前那个 |
| 无清单 | 删掉 `staticfiles.json` | 什么都不删 |
| 容器 | `docker build`、`caddy validate`、compose 解析 | 都通过 |
| 清理 | **全库计数** | 只剩骨架 |

## 自查中发现并已修掉

### A1 备份的是错的数据库文件（严重）

命令第一版写的是 `sqlite3.connect(f"file:{settings.DATABASE_PATH}?mode=ro")`。看起来天经地义，但 `DATABASE_PATH` 只是**配置的默认值**，实际连的是哪个库由 `connection.settings_dict["NAME"]` 决定。测试环境下 Django 会换成 `TEST["NAME"]`（本项目是 `data/test.sqlite3`），于是：

- 测试里备份出来的快照是**开发库**的内容，不是测试库的，所以 `test_the_snapshot_is_a_readable_database` 断言查不到刚建的用户。
- 更要命的是，将来只要有人改了 `DATABASES["default"]["NAME"]` 而没同步改 `DATABASE_PATH`（多库、只读副本、临时切换），**备份就会悄悄备份错的文件**，而且不会报错。

抽了 `core/dbfile.py`，`backup` / `restore` / `optimize_db` 三条命令统一以连接为准。

**这个 bug 是被测试逼出来的**：如果只在开发环境手工跑一次 `manage.py backup`，两个路径恰好一样，永远不会发现。

### A2 恢复时「先复制、后删 WAL」的顺序是错的（严重）

第一版：

```python
shutil.copy2(snapshot, database)      # 先把新库放进去
for path in wal_siblings(database):   # 再删旧 WAL
    path.unlink()
```

问题：Django 的连接还开着，旧 WAL 还在。新数据库文件一落地，SQLite 有可能把**旧库的 WAL 内容**当成这个新文件的未提交事务去处理——轻则恢复出来的数据不对，重则文件损坏。

改成：关连接 → 删 WAL → 再复制。

**这不是理论风险**：我把顺序改回去做变异测试，`test_restore_replaces_the_database_and_clears_prerendered` 直接红了——数据根本没恢复回来。也就是说第一版的恢复**是坏的**，只是演练时因为时序凑巧看着像成功。

加了一条 `test_restore_clears_the_wal_before_writing_the_new_database`，用 monkeypatch 记录 `unlink` 和 `copy2` 的调用顺序，断言复制是最后一步。

### A3 `optimize_db` 在数据库忙的时候会崩

`PRAGMA wal_checkpoint(TRUNCATE)` 需要其他连接都空闲。测试里第一次跑就抛了 `database table is locked`。

设计让它每周日 04:30 跑，那个点 worker 完全可能正在写。检查点做不成只是 WAL 大一点，不值得让 cron 报错发告警。改成捕获 `OperationalError` 并打印一条警告。

### A4 `.gitignore` 里没有 `backups/`

备份文件里有用户邮箱、QQ、微信、手机号。目录之前没被忽略，任何一次 `git add -A` 都可能把它提交上去。已加，并用 `git check-ignore` 确认生效。

## 未完成（重要）

**备份加密和异地同步没有做。** 设计 16.7 第 3 步：「同步一份到服务器以外的位置……**上传前先加密**（比如用 age 加密文件）」。

现在的状态是：本地有一份未加密的备份，保留 14 天。**服务器没了备份就跟着没了。** 这是上线前的硬性缺口，不是可选项。

没做的原因是没有凭据也没法验证——硬写一个跑不通的上传命令不如不写。`crontab.example` 和 README 里都写明了这件事，`backup` 命令每次都会打印「未加密」的警告。

**等用户定了对象存储和加密方案，这应该是 023 的第一件事。**

## 建议

1. **备份恢复演练要在真实服务器上再做一次**。这轮是在开发机上做的，和生产的差别是：生产要先停 `web` 和 `worker`（我的命令做不了这一步，只是提示），而且 media 体量大得多。
2. **考虑给 `backup` 加一个 `--check` 参数**，备份完立刻打开快照跑一次 `PRAGMA integrity_check`。测试里验证了这件事，但命令本身没做，而一个坏掉的备份要到恢复时才会发现。
3. 设计 16.7 提到的 Litestream（持续同步）值得在决定对象存储方案时一起考虑。

## 认可的判断

1. 用 SQLite 的在线备份 API 而不是复制文件——并且用「一边写一边备份」的测试证明了这个选择是必要的（`PRAGMA integrity_check` = ok）。
2. 恢复前校验 `FIELD_ENCRYPTION_KEY`，**在动任何文件之前**。恢复出一库解不开的密文比恢复失败糟糕得多，因为它看起来是成功的。
3. `cleanup_static` 读不到清单就什么都不删。宁可留着垃圾文件，也不能把还在用的资源删掉。
4. 恢复默认是演练，必须 `--yes` 才动手。

## 文档更新

- `docs/design.md` 本轮**没有改动**。
- `README.md` 加了「备份与恢复」「定时维护」两节。
- `deploy/crontab.example` 六条全部放开；`deploy/docker-compose.yml` 补了 `backups` 数据卷。
- `.gitignore` 加了 `backups/`。
- `handoff/STATUS.md` 轮次表加 022，M7 标记为进行中。
