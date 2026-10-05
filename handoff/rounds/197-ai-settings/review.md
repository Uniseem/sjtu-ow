# 197 AI 审核的设置搬进后台（自查）

**结论：通过。** Claude 实现并自查，未经独立复核。

| 要求（`request.md` 验收标准） | 结果 |
|---|---|
| 后台填了密钥就能送审，不用碰 `.env`、不用重启 | `get_provider()` 和 `is_configured()` 每次读全站设置（`test_the_provider_comes_from_the_settings_row`、`test_a_key_or_an_address_is_enough_and_nothing_else_is_read`）；环境变量从设置里删了（`test_the_environment_variables_are_gone`） |
| 密钥是密文、看不到、空着不清 | 直接读数据库列只有密文；页面上没有密钥原文、写着「已保存」；空着保存后还是原来的（新后台和 `/wagtail/` 两个表单都测了） |
| 旧测试改成测全站设置，新规则拆掉就红 | 12 处旧测试改了；18 处变异全部被抓到 |
| 整组检查全绿、正式站升级 | 测试机 1787 条全过；先备份，迁移应用，正式站页面检查正常 |

## 自己挑的刺

- **密钥进了数据库**：这是用户的决定，和 SMTP 密码同一种处理（`FIELD_ENCRYPTION_KEY` 加密，备份里只有密文）。代价：`FIELD_ENCRYPTION_KEY` 丢了，这把密钥要重新填；能进 `/wagtail/` 或服务器 shell 的人能读到明文——以前放在 `.env` 里也一样
- **附加参数只挡了三个键**：`model`、`response_format`、`max_tokens` 这些也能被它改掉（比如把结构化输出关了，结果会变成「无法判定」）。只有超级管理员能改全站设置，挡太多反而碍事；真改坏了「试一下 AI」能看出来
- **没法清空已保存的密钥**：和 SMTP 密码一样；以后要做，可以给密钥框旁边加一个「清除」勾选
- 生产 `.env` 里两行空的 `MODERATION_*` 没删
