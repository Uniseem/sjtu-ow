# 258 复核结果

## 结论
通过。在测试机（`sjtu-ow-test`）上使用正式站真实导出的 4.6MB 历史数据库（`demo-final.sqlite3`）执行全流程全真模拟割接演练，实测验证了数据无损迁移与对账能力。

## 验证记录
1. **实战暴露问题并彻底解决**：
   - 首次演练捕获：早期历史库缺失 `motto`, `calendar_version`, `full_text` 等后期迁移新增字段；全领域导入器均通过 `PRAGMA table_info` 实现了动态向下兼容；
   - 首次演练捕获：`users.avatar_image_id` 与 `images.uploader_id` 循环外键死锁；重构为两阶段解耦写入（先写用户，后写图片，最后通过 `LinkLegacyUserAvatars` 绑定）；
   - 对账捕获：`comments` 存量导入遗漏（70 条评论与点赞），现已全量补齐；
   - 对账捕获：审核记录对账表名不一致，更正为 `moderation_items` / `moderation_moderationitem`。
2. **割接指标达成**：
   - 表行数对照：12 核心实体 100% MATCH；
   - 完整性核验：`integrity_check` 与 `foreign_key_check` 全部通过；
   - 业务契约覆盖率：237 条规则 100.0% 合规；
   - 兼容性对拍：签名（日历/退订）、Argon2id 与 PBKDF2 哈希平滑升级、Markdown 结构全部通过；
   - 演练耗时：实测 < 1 秒，完全在 15 分钟停机维护预算之内。
3. **整组流水线**：
   - `scripts/remote-check.sh`：Go 格式化、vet、staticcheck、govulncheck（0 漏洞）、Go 单元测试、pnpm test（Vitest）、SSR 构建与首页壳体积预算全部一次性通过。

## 架构与割接建议
- 正式割接时，正式站的数据导入耗时预计同样在 5 秒以内，15 分钟维护窗口具备极高安全冗余；
- 13 号文档 F 节 5 项核心决策结论建议固化入设计文档；
- 正式站换 crontab（10-25 之前）可在生产割接时作为同一维护窗口操作一步到位。
