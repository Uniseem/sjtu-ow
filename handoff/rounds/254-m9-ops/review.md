# 254 M9 运维体系：独立复核

## 1. 业务规则与架构设计符合度

- **SQLite 原子快照 (VACUUM INTO)**: 检查 `server/internal/ops/backup.go`，使用 `VACUUM INTO` 导出事务一致的副本，不撕裂 WAL，无需关闭写连接。
- **文件打包与防目录遍历 (safeJoin)**: 检查 `safeJoin` 工具函数，对所有归档解包条目进行了 `..` 和绝对路径过滤，防止恶意覆盖系统文件。
- **解包不落 /tmp (09-5 准则)**: 检查 `server/internal/ops/restore.go`，恢复解包在 `dataDir` 下创建 `0700` 临时目录，不污染 `/tmp`，同文件系统原子替换。
- **完整性与外键校验**: 检查 `PRAGMA integrity_check` 与 `PRAGMA foreign_key_check`，演练与真实恢复均必须校验通过才允许成功。
- **服务端背书超管 (规则 15)**: `createsuperuser` 直接设置 `email_verified_at`、启用状态与超管标志，执行 Django 兼容 Argon2id 哈希。
- **Caddy 路由安全 (12 号文档 3.4)**: `/media/*` 默认 404 隐藏原图，缩略图缓存 1 年，缺失转发 Go 懒生成；静态分块 immutable。

## 2. 自动化测试与检查覆盖

- `server/internal/ops/backup_test.go`:
  - `TestBackupAndRestore`: 验证热备份生成、清单字段、dry-run 演练（不改变现有状态）、正式 restore（还原超管数据与图片文件）。
  - `TestCreateSuperuser`: 验证弱密码拦截、重复邮箱拦截、成功创建字段与已验证状态。
  - `TestReconcile`: 验证数据库完整性自检与报告输出格式。
- `cmd/sjtuow`:
  - 成功接入 `backup`, `restore`, `createsuperuser`, `reconcile` 子命令并编译通过。

## 3. 结论

- M9 运维与生命周期管理命令、备份恢复、容器化配置及升级演练全量完成并验证通过。
