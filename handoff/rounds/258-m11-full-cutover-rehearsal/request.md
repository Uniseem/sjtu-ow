# 258 生产割接全真演练与存量导入全栈加固

## 背景
用户发出「开始吧」与「全部」指令，要求推进割接全真演练、正式站运维与升级准备、以及 13 号文档 F 节 5 项核心决策落地。
在测试机上使用正式站 4.6MB 真实历史数据（`demo-final.sqlite3`）执行全真模拟割接演练时，暴露了跨版本历史库模式字段缺失、用户与图片循环外键依赖、存量评论导入缺失等关键缺陷。本轮将全面加固存量导入管线并达成 100% 对账全绿。

## 本轮范围
1. 增强各领域存量导入器的历史版本兼容性：动态适配 `accounts_user`、`teams_team`、`tournaments_tournament`、`scrims_scrim`、`content_articlepage`、`content_sitepage`、`moderation_moderationitem`、`core_sitesettings` 等表中在早期版本不存在的字段；
2. 解耦用户与图片的双向循环外键依赖：先安全入库用户，后入库图片，并在内容域之后由 `LinkLegacyUserAvatars` 补齐用户头像与头像审核记录的外键；
3. 补齐存量评论与点赞记录导入逻辑（`comments_comment` -> `comments`, `comments_commentlike` -> `comment_likes`）；
4. 修正 `reconcile.go` 中审核记录对账表名映射（`moderation_items` vs `moderation_moderationitem`）；
5. 在测试机上基于真实 4.6MB 快照执行 `deploy/rehearse.sh`，达成全域 12 项实体 100% 行数 MATCH 与一致性 PASS；
6. 测试机整组检查（Go + Web）全绿。

## 明确不做什么
- 不直接覆写正式站生产数据（割接执行需在演练全绿并留存好最新备份后按剧本由用户/运维窗口统一切换）。
- 不破坏 237 条业务契约规则。

## 验收标准
- `deploy/rehearse.sh` 在测试机上成功通过，全流程耗时 < 15 分钟（实测 ≤ 2 秒）；
- `sjtuow reconcile` 12 实体行数 100% MATCH，integrity_check 与 foreign_key_check 全 PASS；
- `sjtuow rulecheck` 达成 100.0% 合规覆盖；
- `sjtuow parity` 签名、密码哈希与渲染对拍全 PASS；
- `scripts/remote-check.sh` 编译、代码检查、Go 单测、Web 构建与单测、体积预算全绿。
