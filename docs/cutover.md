# SJTU-OW 生产割接操作剧本与应急回滚预案 (M10/M11)

本文档是现行 Django 站向 Vue 3 + Go 新栈平滑割接的**官方操作剧本**（依据 `docs/rewrite-research/12-architecture.md` 第 8 节与第 13 节）。

---

## 1. 割接目标与不变量

1. **零数据丢失**：正式停机后以 SQLite 原生只读快照导出全部业务数据；
2. **全编号沿用**：用户、战队、赛事、文章、图片编号 100% 保持原样，外链与公开 URL 零断链；
3. **安全凭证无缝迁移**：
   - 存量密码（Argon2id 与 PBKDF2）完全继承，割接后用户无须重置密码；
   - 现存日历订阅链接与退订链接（`SIGNING_KEY` = 旧 `DJANGO_SECRET_KEY`）100% 持续有效；
   - 数据库敏感密文字段（`FIELD_ENCRYPTION_KEY`）平滑继承；
4. **会话处理**：全员重新登录（提前在 QQ 交流群及站内公告声明）；
5. **门禁红线**：割接流水线中 `sjtuow reconcile` 对账自检**不全绿绝不开站**。

---

## 2. 停机割接时间窗口与耗时模型

基于测试机 staging 演练实测，停机维护窗口预估 **15 分钟**（预留冗余至 30 分钟）。

| 序号 | 阶段步骤 | 执行命令/动作 | 预估耗时 | 责任人 |
|---|---|---|---|---|
| T-7d | 提前公告 | QQ 群、站内首页发布停机维护与重新登录预告 | — | 管理员 |
| T-0 | 进入维护期 | Caddy 切换至静态维护页，切断外部写流量 | 10 秒 | 运维 |
| T+1m | 停止旧站写容器 | `docker compose stop web worker` | 20 秒 | 运维 |
| T+2m | 生产最终热备 | 导出最终 `db.sqlite3` 与 `media/` | 1 分钟 | 自动化 |
| T+3m | 数据完整导入 | `sjtuow import /data/legacy.sqlite3` | 1 分钟 | 自动化 |
| T+4m | 全域数据对账 | `sjtuow reconcile /data/legacy.sqlite3` | 30 秒 | 自动化 |
| T+5m | 启动新栈集群 | `docker compose -f deploy/docker-compose.new.yml up -d` | 30 秒 | 自动化 |
| T+6m | 服务自检冒烟 | `/healthz` 写探测与关键页面探针 | 1 分钟 | 运维 |
| T+7m | 切换反代流量 | Caddy 切至生产新栈路由，下线维护页 | 10 秒 | 运维 |
| T+8m | 生产联调验证 | 超管登录、查看赛事/内战/文章、测试发信 | 3 分钟 | 站长/干部 |

---

## 3. 标准割接执行步骤

### 步骤零：staging 全流程模拟演练（割接前至少演练两次）

依据 `12-architecture.md` 第 8.4 节要求，割接前必须在 staging（测试机）使用正式站备份完整演练至少两次：

```bash
# 执行模拟演练流水线并记录各阶段耗时
bash deploy/rehearse.sh /srv/sjtu-ow/data/demo-final.sqlite3

# 执行端到端新旧对拍与兼容性核验
sjtuow parity --new-url http://127.0.0.1:4000 --media-dir /srv/sjtu-ow/data/media
```

演练报告输出 5 项关键指标（快照、模式迁移、全域导入、对账自检、契约审计与对拍），耗时必须严格控制在 900 秒（15 分钟）以内。

### 步骤一：前置检查（割接前 30 分钟）

```bash
# 1. 验证新镜像与配置完整性
cd /srv/sjtu-ow
docker compose -f deploy/docker-compose.new.yml config

# 2. 验证宿主环境变量
test -n "$SIGNING_KEY" && test -n "$FIELD_ENCRYPTION_KEY" && echo "密钥完整"
```

### 步骤二：自动化割接执行

执行封装好的割接脚本：
```bash
bash deploy/cutover.sh
```

流水线内部自动执行：
1. **下发维护页**：Caddy 重载至 `deploy/maintenance.html`，外部写请求全部友好拦截；
2. **冻结旧站写入**：停止 Django 容器；
3. **最终数据镜像**：原子快照生成 `/srv/sjtu-ow/data/legacy-final.sqlite3`；
4. **全新新库构建**：`sjtuow migrate` 初始化空库；
5. **全领域无损导入**：按「设置 → 账号与角色 → 战队 → 分组 → 赛事 → 内战 → 页面与分类 → 评论 → 审核」流水线只读导入；
6. **对账门禁拦截**：执行 `sjtuow reconcile`，核对行数与外键，不通过则自动中断并回滚；
7. **启动新栈容器**：启动 Go 后端、Worker、Vue 3 SSR 与 Caddy 反代；
8. **健康冒烟探测**：循环等待 `/healthz` 响应 200。

### 步骤三：割接后验证清单（Checklist）

1. [ ] 访客访问首页：页面极速服务端渲染，首屏加载条正常，样式/深色主题无错乱；
2. [ ] 访客访问 `/news/` 资讯：存量文章正常排版，Markdown 图注与 B 站内嵌正常；
3. [ ] 现有账号登录：使用旧密码成功登录，跳转个人资料中心；
4. [ ] 超级管理员进入 `/admin/`：八大类管理导航可用，待办事项无异常堆积；
5. [ ] 检查 `/healthz`：数据库写入探测正常，数据卷剩余空间充足，Worker 120 秒心跳活跃。

---

## 4. 48 小时应急回滚预案（Rollback）

如果在割接上线后 48 小时内发现未预期的重大致命缺陷（如数据损坏、核心权限失控）：

> [!CAUTION]
> 割接 48 小时内旧站镜像与最终备份数据库处于只读留存状态，支持一键无缝秒级回滚。

### 回滚命令

```bash
# 1. 停止新栈服务
docker compose -f deploy/docker-compose.new.yml down

# 2. 恢复旧站 Compose 拓扑
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.vps.yml up -d

# 3. 校验旧站健康状态
curl -f http://127.0.0.1:22887/healthz
```

48 小时窗口过后，新站产生大量新业务数据，原则上不再回滚，遇问题一律向前修补升级。

---

## 5. 2026-10-10 的回滚（265）和学到的

259 割接后前台没做完（`docs/frontend-migration.md`），用户 10-10 决定回滚，265 在窗口内做完：旧库和割接前的快照逐字节一致，新栈割接后没有写进新数据，停机约 1 分钟。经过和日志在 `handoff/rounds/265-rollback-to-legacy/`。

上面第 4 节的「回滚命令」**照做会失败**：新栈和旧站用同一个 Compose 项目名 `sjtu-ow`、同样叫 `web`、`worker` 的服务，构建新栈时把旧站镜像的标签（`sjtu-ow-web:latest`、`sjtu-ow-worker:latest`）占了，`up -d` 起的「旧站」其实是新栈的镜像。265 是先重新构建旧镜像再切的。下一次割接：

1. 割接前先给旧镜像另打标签：`docker tag sjtu-ow-web:latest sjtu-ow-web:legacy`（worker 同样），回滚时让旧站的 Compose 用这个标签
2. 新栈换一个项目名或服务名（比如项目 `sjtu-ow-next`），两套不共用镜像名
3. 停新栈、起旧站的命令都带 `--env-file /srv/sjtu-ow/.env`
4. 恢复定时任务：割接时改过的 `/etc/cron.d/sjtu-ow` 要先备份，回滚时换回
