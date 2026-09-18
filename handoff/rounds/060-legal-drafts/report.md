# 060 实现报告

## 结论

**完成。** 两份草稿在 `content/legal/terms.md`、`content/legal/privacy.md`，新命令 `load_legal_pages` 把它们发布到网站的「用户协议」「隐私政策」页面。**【】里的内容要社团填写或决定。**

## 起草时逐条核对的

隐私政策里每一条关于数据的说法都对照了代码。核对中**改掉了一句不成立的**，**翻出了两件运维问题**：

| 说法 | 核对 | 结果 |
|---|---|---|
| 联系方式有 QQ、微信、手机号、其他 | `accounts.models.ContactType` | 对 |
| 邮箱只有超级管理员能看到 | 赛事审核后台、CSV 导出、内战分队页、战队管理页里搜 `email` | 都没有，对 |
| 给上游赛事平台的数据 | `integrations/serializers.py` 的 `MEMBER_FIELDS` 和段位 | 昵称、游戏 ID、是否交大、是否队长、段位；**没有联系方式**。照实写 |
| 「报名页面会写明该赛事由谁审核」 | 搜公开页面模板里的 `review_mode` | **不成立**：只有后台审核页显示。改成「赛事说明里写明」并标【】提醒赛事管理员 |
| 访客 IP | `core/ratelimit.py`、gunicorn 和 Caddy 的日志配置 | 只在限流时短暂使用；gunicorn 看到的是 Caddy 的地址，Caddy 没开访问日志。写「不单独记录访问日志」 |
| 备份保留期 | `backup` 命令 | 本地 14 天会清理；**上传到 R2 的没有清理**，一直留着。写成【】请社团定，同时记为运维问题 |
| 后台记录保留期 | `cleanup_old_data` | 任务记录 30 天、处理过的审核记录 180 天，照实写 |
| 用户的权利 | 058 的导出和注销 | 对，注销后的处理和设计 3.8 一致 |

**运维问题**（记进 `STATUS.md`）：R2 上的备份没有保留期；Docker 日志没设大小上限。

设计 15.3 要求隐私政策写明的：存储国家或地区、服务商、处理目的、保存期限、查询更正删除方式、第三方 AI 服务名称——都有，前两项是【】。

## 用户协议

按网站实际的功能写：账号（「是否来自交大」会决定仅限交大的赛事和内战资格）、行为规范（设计 5.5 的审核维度：代打、卖号、外挂交易等）、用户内容的授权、战队赛事内战的规则（名单锁定、如实填写段位）、管理措施（对应后台真有的操作：关闭车帖、功能权限、驳回报名、停用账号）、服务说明（服务器在境外、微信可能限制）。

## 发布命令

`python manage.py load_legal_pages`：

- 把草稿里用到的那点 Markdown（`##`、`###`、`-` 和 `1.` 列表、`**加粗**`）转成网页正文，页面标题用后台的标题，所以草稿自己的 `#` 标题去掉；草稿开头的说明注释去掉；其余文字转义
- **页面已经有正文时默认跳过**，加 `--force` 才覆盖——避免把社团在后台改好的内容冲掉
- 页面正文编辑器不支持表格和多级列表，所以草稿里没用

草稿放在 `content/legal/` 而不是 `docs/`：`.dockerignore` 排除了 `docs/`，放那里镜像里就没有，服务器上运行命令会找不到文件。

## 测试

`content/tests/test_legal_pages.py`，5 条：Markdown 转换；草稿里的 HTML 被转义；两份草稿发布后页面上有正文、没有残留的 `**` 和 `##`；已有正文时不覆盖、`--force` 覆盖；隐私政策里写到了网站实际用的每个第三方（DeepSeek、Cloudflare、发信服务商）和 058 做的导出、注销。

最后那条是**让文字和代码绑在一起**：以后换了审核服务商或者去掉了导出功能，改代码的人会看到这条测试红了，想起来要改隐私政策。

## 验收输出

和 058 同一次全量运行（草稿和测试已经在工作区里）：

```
$ ruff check . && ruff format --check .
All checks passed!
228 files already formatted

$ uv run python -m pytest -q
FAILED scrims/tests/test_teaming.py::test_6v6_finishes_within_a_second - Asse...
1 failed, 735 passed in 214.07s (0:03:34)
```

失败的是负载下的计时测试，见 058 报告。

## 改动文件

```
content/legal/terms.md、content/legal/privacy.md          新建，草稿
content/management/commands/load_legal_pages.py          新建
content/management/__init__.py、commands/__init__.py     新建
content/tests/test_legal_pages.py                        新建，5 条
README.md                                                「用户协议与隐私政策」一节
handoff/STATUS.md
handoff/rounds/060-legal-drafts/
```
