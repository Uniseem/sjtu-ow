# 新栈割接与回滚剧本

仅在用户批准的本批必要验收完成、用户明确授权割接时间及正式站操作后执行。299起剩余验收按 [开发与验收的本批范围](development.md#本批剩余验收范围299-用户决定)，不再要求追加全量矩阵或第二次演练。当前部署与授权状态见 handoff/STATUS.md。割接前不部署试用站、不安排干部试用（291 用户确认）。

## 1. 前提与数据边界

- 本批沿用既有通过的整组、精确SHA的CI、响应头、预算与真实旧库演练证据，仅完成299保留的操作检查；其余追加验收按用户决定取消。省略项不称通过。演练实际耗时只作参考，不直接承诺正式站停机时间。
- 正式站是真实数据，禁止用旧备份覆盖当前库。旧 Django 库、媒体、容器及镜像保留，旧库不做新栈迁移。
- 新栈独立 Compose 项目 `sjtu-ow-next`，镜像 `sjtu-ow-next-server:latest`、`sjtu-ow-next-web:latest`；新媒体卷默认 `sjtu-ow-next_media`，不能共享可写旧媒体卷。
- 新栈单独环境文件 `/srv/sjtu-ow/.env.next`，旧站仍 `.env`。SITE_URL 相同；SIGNING_KEY 必须沿用旧 DJANGO_SECRET_KEY，FIELD_ENCRYPTION_KEY/BACKUP_ENCRYPTION_KEY 沿用旧密钥。仅在服务器环境文件中配置，不回显或提交。
- 新库为空才可导入；编号、密码、签名地址、冻结信、图片与字体均从最新旧库和媒体只读迁入。现有会话需要重新登录。

## 2. 授权后的预检与演练边界

机器访问与备份操作先读 operations.md。磁盘清理按本轮用户授权执行；296此前不清理的决定已被301明确授权覆盖，当轮范围以request和STATUS为准。R2异地备份仍不配置、不追加测试。割接脚本始终只读检查磁盘，要求本站目录所在盘至少25%且5GiB空闲，不足就停止并报告，不会自动清理。299取消追加外部网络与邮箱专项，不再把它们列为本批前置任务。

299本批沿用既有真实旧库演练结果，不再执行第二场；本轮文档调整也不访问服务器或启动演练。下面保留演练操作方法，只有以后用户另行要求时才执行，不从本节自动领取追加任务：

测试机演练的输入必须明确存在，不回退空库：

```bash
bash deploy/rehearse.sh /srv/sjtu-ow-rehearsal/latest.tar.gz
# 或已有只读旧库与旧媒体
bash deploy/rehearse.sh /srv/sjtu-ow-rehearsal/db.sqlite3 /srv/sjtu-ow-rehearsal/media
```

脚本安全解包、SQLite backup（含 WAL）→ migrate → import → import-media → import-fonts → reconcile → rulecheck → parity，逐步计时并检查900秒预算。原始数据及诊断仅留权限700的测试目录，用完删除；日志只保留计数、耗时与错误类型。原完整演练方法见 final-batch.md 4.10；299已取消本批追加演练和页面补证。实际割接仍按第3节导入、对账和检查健康状态。

## 3. 正式站文件与执行

正式站旧 `deploy/docker-compose.vps.yml`、`Caddyfile.vps` 不进仓库。新栈不得复用旧覆盖文件。准备并审阅 `deploy/docker-compose.next-vps.yml`（同样不提交）：proxy `ports: !override ["22887:80"]`、挂载 `Caddyfile.next-vps`。后者以仓库 `Caddyfile.new` 为基础；其中已含 `trusted_proxies static private_ranges 100.96.0.0/12` 和 `trusted_proxies_strict`，保留。不要覆盖旧 Caddyfile.vps。

```bash
cd /srv/sjtu-ow
# 仅输出检查结果，绝不打印完整展开配置或环境变量
docker compose -p sjtu-ow-next -f deploy/docker-compose.new.yml -f deploy/docker-compose.next-vps.yml --env-file /srv/sjtu-ow/.env.next config --quiet
# DB 与媒体绝对路径由只读 docker volume inspect /现有 Compose 挂载核实，禁止猜测
CUTOVER_AUTHORIZED=yes bash deploy/cutover.sh "$LEGACY_DB_PATH" "$LEGACY_MEDIA_PATH" /srv/sjtu-ow/.env.next
```

流水线实际行为：

1. 验配置、磁盘、输入和空新库，给**正在运行**的旧 web/worker 镜像按 image ID 打 legacy 标签，留项目专用回滚覆盖文件与 cron 备份。
2. 用隔离名称提前构建新镜像，不碰旧标签。
3. 分别 TERM 停旧 worker、web；把 `/etc/cron.d/sjtu-ow` 移到本次备份目录（不是 cron.d 内改名）。新 worker 按 Asia/Shanghai 自行定时，不能再让宿主 cron 调 manage.py。
4. 旧库原生 SQLite backup；导出的副本转为DELETE journal，文件600、宿主父目录700，并供非root导入器UID10001读取。旧库自身的journal与数据不改变。新库迁移、导入、图片和字体、对账，不通过不开新站。新站尚未启动接流量时，可恢复保留的旧服务/cron后修复重试；重试使用独立空新卷，保留失败库。新站已启动可能写入后，按下节确认数据差异再决定回退。
5. 停旧 proxy，起新栈；健康检查。此后可能已有新写入，禁止自动用旧库覆盖。

割接后验证访客主要页、旧密码登录、七身份门、真实图片、超管后台及 worker 心跳；收信和外部网络/监控按用户批准的清单验。明确公告重新登录。实际结果写 STATUS。

## 4. 回滚：先确认新写入，再切服务

不能承诺48小时内无损秒回滚。只要新站有一条写入，时间再短也必须先保全新库/媒体，评估差异，取得用户的数据处理决定；禁止直接恢复旧备份。以下命令仅用于**确认新站尚无业务写入，或用户已决定差异处理**之后：

```bash
cd /srv/sjtu-ow
# BACKUP_DIR 为 cutover.sh 输出的本轮项目备份目录，不用“最新一个”猜
# 保留新旧数据卷与容器，不 down -v
docker compose -p sjtu-ow-next -f deploy/docker-compose.new.yml -f deploy/docker-compose.next-vps.yml --env-file /srv/sjtu-ow/.env.next stop worker
docker compose -p sjtu-ow-next -f deploy/docker-compose.new.yml -f deploy/docker-compose.next-vps.yml --env-file /srv/sjtu-ow/.env.next stop server web proxy
# 旧库从未修改，不需要也不允许整库覆盖
cp -p "$BACKUP_DIR/cron.d-sjtu-ow" /etc/cron.d/sjtu-ow
docker compose -p sjtu-ow -f deploy/docker-compose.yml -f deploy/docker-compose.vps.yml -f "$BACKUP_DIR/legacy-images.yml" --env-file /srv/sjtu-ow/.env up -d --no-build
curl --fail --silent http://127.0.0.1:22887/healthz
```

若未配置新栈专用覆盖文件，命令里的相应 `-f` 可省略，其他参数完整保留。旧镜像已 pin，不需现场重建；旧 cron 恢复到北京时间判定版本。回滚成功需核对 Compose 镜像 ID、访客页面、备份/预渲染及真实数据计数，结果照实记录。

---

## 5. 2026-10-10 的回滚（265）和学到的

259 割接后前台没做完（`docs/frontend-migration.md`），用户 10-10 决定回滚，265 在窗口内做完：旧库和割接前的快照逐字节一致，新栈割接后没有写进新数据，停机约 1 分钟。经过和日志在 `handoff/rounds/265-rollback-to-legacy/`。

上面第 4 节的「回滚命令」**照做会失败**：新栈和旧站用同一个 Compose 项目名 `sjtu-ow`、同样叫 `web`、`worker` 的服务，构建新栈时把旧站镜像的标签（`sjtu-ow-web:latest`、`sjtu-ow-worker:latest`）占了，`up -d` 起的「旧站」其实是新栈的镜像。265 是先重新构建旧镜像再切的。下一次割接：

1. 割接前先给旧镜像另打标签：`docker tag sjtu-ow-web:latest sjtu-ow-web:legacy`（worker 同样），回滚时让旧站的 Compose 用这个标签
2. 新栈换一个项目名或服务名（比如项目 `sjtu-ow-next`），两套不共用镜像名
3. 停新栈、起旧站的命令都带 `--env-file /srv/sjtu-ow/.env`
4. 恢复定时任务：割接时改过的 `/etc/cron.d/sjtu-ow` 要先备份，回滚时换回


293 轮更正：上面保留的是265历史教训，现行操作已落实在第1–4节及脚本；新旧项目/镜像/媒体隔离、正在运行镜像pin、所有Compose命令带环境文件、停用/恢复宿主cron、原库不覆盖。旧版“48小时内一键无损回滚”的承诺已撤销。
