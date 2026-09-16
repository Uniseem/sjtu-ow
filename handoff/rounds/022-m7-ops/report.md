# 022 实现报告

> 本轮由实现方（Claude）自己做，用户外出。下面所有输出都是真实跑出来的；没跑的会写「未验证」。

## 结论

**完成。** 设计 16.5 和 16.7 要求的四条命令补齐了：`backup`、`restore`、`cleanup_static`、`optimize_db`。019 写 crontab 时注释掉的三条现在都能放开。

**做了一次真实的备份恢复演练**：造数据 → 备份 → 删掉 → 恢复 → 验证，包括加密字段能不能解开。过程中发现并修掉了两个真问题：命令备份的是**配置里的数据库路径而不是实际连接的那个文件**，以及恢复时**先复制后删 WAL 的顺序是错的**（会让恢复失败）。

## 逐条结果

### T1 `manage.py backup`

用 `sqlite3.Connection.backup()`（在线备份 API）生成快照，打包成 `sjtu-ow-<时间戳>.tar.gz`，含 `db.sqlite3` 和 `media/`。`--output`、`--keep-days` 可选，默认保留 14 天。每次都提醒「备份未加密」。

### T2 `manage.py restore`

顺序：校验 `FIELD_ENCRYPTION_KEY` → 关闭数据库连接 → 删除旧 WAL → 替换数据库 → 恢复 media → 清空 `prerendered` 及其记录表。不加 `--yes` 只打印计划。停止和启动服务做不了，输出里提示。

### T3 `manage.py cleanup_static`

按 `staticfiles.json` 判断在用的文件，删除「不在清单里」**且**「超过 30 天」的。**读不到清单就什么都不删**。有 `--dry-run` 和 `--keep-days`。

### T4 `manage.py optimize_db`

`PRAGMA optimize` + WAL 检查点，报告前后的数据库和 WAL 大小。`--vacuum` 可选。

### T5 crontab 与文档

`deploy/crontab.example` 六条全部放开，另外把 019 留下的 `deliver_due_webhooks` 兜底任务也接上了（每 10 分钟扫一次到期未投递的 Webhook），并加了「上传到对象存储还没做成命令」的说明。`deploy/docker-compose.yml` 补了 `backups` 数据卷（设计 16.2 的表里有，之前漏了）并挂到 `web`。README 加了「备份与恢复」和「定时维护」两节。`.gitignore` 加了 `backups/`。

## 验收输出

### 1. 检查与测试

```
$ ruff check . && ruff format --check .
All checks passed!
200 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ uv run python -m pytest -q
511 passed in 35.58s

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

本轮新增 19 个测试。

### 2. 完整的备份恢复演练

**造数据**：一个用户（含游戏 ID 和 QQ）、一个 API 客户端（Secret 是加密字段）。

```
用户 112 客户端 ak_f14e705eed53
SECRET JUBDUMP6ZNwfm2ekhab1O-Pboqi7fXaOzjIEtv3QNFY
```

**步骤 1：备份**

```
$ uv run python manage.py backup
已备份到 /Users/.../backups/sjtu-ow-20260916-221549.tar.gz（0.1 MB）
备份里有用户邮箱和联系方式，且没有加密。上传到服务器以外的位置之前先加密（设计 16.7）。
```

**步骤 2：破坏数据**

```
删除演练用户: (4, {...'accounts.User': 1})
删除演练客户端: (1, {'integrations.ApiClient': 1})
现在：用户 0 客户端 0
```

**步骤 3：先演练（不加 `--yes`）**

```
FIELD_ENCRYPTION_KEY 校验通过。
  - 用备份里的数据库替换 /Users/.../data/db.sqlite3
  - 删除 WAL 文件：/Users/.../data/db.sqlite3-wal, /Users/.../data/db.sqlite3-shm
  - 恢复 media 到 /Users/.../media
  - 清空 /Users/.../prerendered
这是演练，什么都没有改。加 --yes 才会执行。
```

**步骤 4：真的恢复**

```
FIELD_ENCRYPTION_KEY 校验通过。
  - ...（同上四条）
恢复完成。
接下来（设计 16.7）：启动 web 和 worker，在后台触发全量重新生成，检查 /healthz 和关键页面。
```

**步骤 5：验证**

```
用户: 演练用户 | 游戏 ID: Drill#0022
联系方式: 987654321
客户端: ak_f14e705eed53
加密字段能否解开 → Secret: JUBDUMP6ZNwfm2ekhab1O-Pboqi7fXaOzjIEtv3QNFY
```

最后一行和创建时打印的 Secret **一模一样**——加密字段完整地过了一遍备份和恢复。`prerendered/` 恢复后是空的。

### 3. 备份文件的内容

```
$ ls -lh backups/
-rw-r--r--  1 ...  111K Sep 16 22:15 sjtu-ow-20260916-221549.tar.gz

$ tar tzf backups/*.tar.gz | head -8
db.sqlite3
media/
media/.gitkeep
media/fonts/
media/fonts/css/
media/fonts/css/fonts.f42c1154633c.css
media/images/
media/images/article-cover_0ijjVF2.2e16d0ba.fill-1200x630.png
  ...共 167 项
```

只有数据库和 media，没有 `prerendered`、没有 `staticfiles`、没有 `.env`（测试里有断言）。

### 4. `FIELD_ENCRYPTION_KEY` 不一致

```
$ FIELD_ENCRYPTION_KEY="a-completely-different-key-0022" uv run python manage.py restore backups/... --yes
CommandError: 当前的 FIELD_ENCRYPTION_KEY 解不开备份里的加密字段：integrations_apiclient.secret。
请换成备份时使用的密钥再恢复（设计 16.7 第 3 步）。
```

点名了具体是哪个字段，而且是在动任何文件**之前**就拒绝。

### 5. `cleanup_static` 与 `optimize_db`

```
$ uv run python manage.py optimize_db
优化前：数据库 1.7 MB，WAL 0.0 MB
优化后：数据库 1.7 MB，WAL 0.0 MB
```

造一个有清单的 static 目录（当前版本 1 个、40 天前的旧文件 1 个、5 天前的 1 个）：

```
$ STATIC_ROOT=/tmp/static-demo ... cleanup_static --dry-run
将删除 1 个旧静态文件（0.0 MB）；保留当前版本的 6 条清单项，另有 1 个文件未超过 30 天。

$ STATIC_ROOT=/tmp/static-demo ... cleanup_static
已删除 1 个旧静态文件（0.0 MB）；保留当前版本的 6 条清单项，另有 1 个文件未超过 30 天。

$ ls /tmp/static-demo/css/
app.new.css      app.recent.css
```

当前版本的留着、5 天前的留着、40 天前的没了。没有清单时：

```
staticfiles.json 不存在或读不出来。没有清单就无法判断哪些文件还在用，什么都不删。
```

### 6. 回归 + docker / caddy / compose

```
$ uv run python -m pytest -q
511 passed in 35.58s

$ docker build -t sjtu-ow:022 .
sha256:ee6d8b05f86a8d95782850433847459255a86046688052236387ba241e4586dc

$ docker run --rm -v ./deploy:/etc/caddy:ro caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile
Valid configuration

compose（这台机器没有 docker compose v2，改用 Python 解析校验）：
services: ['web', 'worker', 'proxy']
volumes : ['data', 'media', 'static', 'prerendered', 'backups', 'caddy_data', 'caddy_config']
web 挂载: [..., 'backups:/app/backups']
```

### 7. 清理（查了全库）

删除演练用户 1 个、客户端 1 个、备份文件 1 个、临时 static 目录。全库计数只剩骨架。

## 设计偏差

**没有改设计文档。** 三点说明：

1. **没有做对象存储上传和 age 加密**（设计 16.7 第 3、4 步）。没有凭据也没法验证，硬写一个跑不通的命令不如不写。`crontab.example` 里留了说明和一行示例，README 里也写明了。**这是这轮最大的缺口。**
2. **没有做 Litestream**（设计 16.7 第 4 步写的是「需要更高可靠性时」，属于可选）。
3. **`optimize_db` 的 WAL 检查点失败时只警告不报错**。设计没写这一格。04:30 跑的时候 worker 很可能正在写，检查点做不了；跳过一次只是 WAL 大一点，不值得让 cron 报错。

## 未完成 / 不同意

1. **备份加密与异地同步**（见上）。这是上线前必须有人做的事，不做完不应该正式上线。
2. M7 剩下的部分——**视觉风格定稿、用户协议和隐私政策正文、生产部署、国内多种网络下的访问测试、备份恢复的真机演练、小范围试运行**——要么等用户拍板，要么必须在真实服务器上做，这轮做不了。
3. 设计 16.8 的升级流程没有脚本化。它主要是人工步骤（通知、停服、迁移、切镜像），写成脚本反而容易出事。

## 顺带发现

1. **命令一开始备份的是错的数据库文件**：`settings.DATABASE_PATH` 是配置的默认值，但实际连的库由 `connection.settings_dict["NAME"]` 决定——测试环境下是 `test.sqlite3`。详见 `review.md` A1。
2. **恢复时「先复制数据库、后删 WAL」是错的**，会让恢复静默失败。详见 `review.md` A2。
3. `.gitignore` 里没有 `backups/`。备份文件里有用户邮箱和联系方式，万一被提交上去就是事故。已加。

## 需要确认

1. **备份加密和异地同步用什么？** age + 对象存储（设计的默认建议），还是别的？需要密钥和凭据，你来定之后我可以做成命令。
2. 018–021 留下的五个问题仍未定。

## 改动文件

```
core/dbfile.py                              新增：以连接为准确定数据库文件位置
core/management/commands/backup.py          新增
core/management/commands/restore.py         新增
core/management/commands/cleanup_static.py  新增
core/management/commands/optimize_db.py     新增
core/tests/test_ops_commands.py             新增 19 个测试
sjtu_ow/settings/base.py                    BACKUP_ROOT、BACKUP_KEEP_DAYS、STATIC_KEEP_DAYS
deploy/docker-compose.yml                   backups 数据卷
deploy/crontab.example                      六条全部放开
.gitignore                                  backups/
README.md                                   备份与恢复、定时维护两节
```
