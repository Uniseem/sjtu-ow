# 031 实现报告

## 结论

**完成。022 轮起挂着的上线阻塞项解决了。** 后台配好 Cloudflare R2 之后，每天的备份会自动加密并上传一份；数据丢了可以 `restore --from-s3` 拿回来。

## 一个设计上的决定：密钥为什么不在后台

用户说「管理员在后台可以设置」。我把**桶的配置**放进了后台，但**加密密钥放在环境变量**，这两者分开是有原因的：

- **桶的凭据**（地址、Key ID、Secret）放数据库没问题。它们是「怎么够到桶」，服务器整个丢了也无所谓——在新机器上重新填一遍就行。
- **加密密钥放数据库就是死循环**：密钥在数据库里 → 数据库被备份 → 备份用这把密钥加密 → 服务器丢了，你手上只有一个加密的备份和一把在备份里面的钥匙。**打不开。**

所以 `BACKUP_ENCRYPTION_KEY` 是环境变量，和 `DJANGO_SECRET_KEY`、`FIELD_ENCRYPTION_KEY` 一样放密码管理工具——这也正是设计 16.7 写的「备份的解密密钥……不和备份文件放在一起」。

写了一条测试盯着这件事：断言 `SiteSettings` 上**没有**任何叫 `backup_encryption_key` / `backup_key` / `backup_secret` / `backup_passphrase` 的字段。以后有人想「放后台更方便」时会被挡下来。

## 完整流程实测

```
=== 1. 备份（后台已开启异地备份）===
已备份到 /tmp/r2demo/sjtu-ow-20260916-233955.tar.gz（0.1 MB）
已加密并上传到 sjtu-ow-backups/sjtu-ow/sjtu-ow-20260916-233955.tar.gz.enc

=== 2. 桶里有什么 ===
  sjtu-ow/sjtu-ow-20260916-233955.tar.gz.enc  0.1 MB  2026-09-16 15:39:55+00:00
用 --from-s3 <KEY> 恢复其中一个。

=== 3. 上传的内容不是明文 ===
  前 16 字节: b'gAAAAABqqrhLro7u'          ← Fernet 密文，不是 gzip 的 1f 8b
  是 gzip 吗: False
  能不能当 tar.gz 打开: 不能（ReadError）✓

=== 4. 换一把钥匙解不开 ===
正在从对象存储下载 sjtu-ow/sjtu-ow-...enc ……
  解不开这个备份：BACKUP_ENCRYPTION_KEY 和加密时用的不是同一个。
```

测试里还验了从桶里恢复能真的拿回数据：建用户 → 备份上传 → 删用户 → **把本地备份整个删掉** → `restore --from-s3` → 用户回来了。

## 几个具体决定

**上传失败 = 命令失败。** 本地备份已经生成了，但没送出去，这时候命令如果返回成功，cron 就不会报警，而你以为异地有一份。所以抛 `CommandError`，消息里说清楚「本地备份已生成，但上传失败」。

**没开异地备份时会每次提醒**：

```
异地备份没有开启。本地这份没有加密，里面有用户邮箱和联系方式，
**服务器没了这份也跟着没了**。在「设置 → 全站设置 → 异地备份」里配置对象存储（设计 16.7）。
```

**本地那份不加密。** 本地备份是给「手滑删了数据、马上恢复」用的，加密只会让恢复多一道手续；真正需要加密的是离开服务器的那份。

**用 Fernet 不是 age。** 设计写的是「比如用 age」——`cryptography` 已经是依赖，SMTP 密码和 API 密钥用的就是它，不值得为此多一个二进制依赖。备份整个读进内存加密，现在 0.1MB 无所谓；media 大起来之后要改成流式，记在这里。

**新增依赖 boto3。** R2 是 S3 兼容的，boto3 指个 `endpoint_url` 就能用。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
207 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ uv run python -m pytest -q
601 passed in 41.24s

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

新增 13 个测试，都用假桶，不连网络、不需要凭据。

## 你要做的事

上线前在「设置 → 全站设置 → 异地备份」里填：

| 项 | Cloudflare R2 填什么 |
|---|---|
| 对象存储地址 | `https://<账号ID>.r2.cloudflarestorage.com` |
| 存储桶 | 你建的桶名 |
| 区域 | `auto` |
| Access Key ID / Secret | R2 的 API 令牌 |
| 路径前缀 | 比如 `sjtu-ow/` |

再在服务器环境变量里设 `BACKUP_ENCRYPTION_KEY`（随便一串足够长的随机字符），**和 `DJANGO_SECRET_KEY` 一起存进社团的密码管理工具，不要只存在某个人电脑上**。

## 未完成

- **大文件流式加密**。现在整个读进内存，media 上了几百 MB 要改。
- **对象存储那边的保留策略**。本地保留 14 天由命令管，桶里留多久建议用 R2 自己的生命周期规则，我没在代码里做。

## 改动文件

```
core/offsite.py                     新增：加密、上传、列表、下载
core/models.py                      SiteSettings 加 7 个异地备份字段
core/migrations/0009_*.py           新增
core/management/commands/backup.py  备份后自动加密上传；--no-upload
core/management/commands/restore.py --list-s3、--from-s3
core/tests/test_offsite_backup.py   新增 13 个测试
sjtu_ow/settings/base.py            BACKUP_ENCRYPTION_KEY
sjtu_ow/settings/prod.py            同上
deploy/crontab.example              说明改写
README.md                           异地备份一节
pyproject.toml                      boto3
```
