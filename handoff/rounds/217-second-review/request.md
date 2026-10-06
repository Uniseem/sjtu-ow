# 217 轮要求：第二次全站复核（只记录，不修）

## 背景

用户 10-07：「派尽量多的子代理，在之前的基础上，继续 review，并且只记录结果不修复」。210 是第一次全站复核，211–216 把它列出的问题全修了（216 修完最后的低严重度条目和四处设计空白）。210 当时有几块「没来得及看」，211–216 又改了不少代码，都需要新的眼睛。

## 范围

做：16 个复核代理并行，各看一块（下表），只读代码、测试、设计；可以在测试机上跑**复现脚本**（放在 `findings/` 下，放后台跑），不改任何业务代码、测试和文档。每个代理把结果写进 `findings/<块>.md`，我汇总成 `review.md`。

| 块 | 文件 |
|---|---|
| 01 内容渲染 | `content/markdown.py`、`embeds.py`、`legacy_body.py`、`article_meta.py`、`blocks.py` |
| 02 图片与头像 | `backoffice/views/images.py`、`moderation/avatar_admin.py`、`accounts/images.py`、`teams/images.py` |
| 03 评论 | `comments/` 全部，含对未发布文章的接口 |
| 04 Wagtail 超管路径 | `/wagtail/`、`wagtail_hooks`、`core/middleware.py`、旧表单 |
| 05 赛事报名 | `tournaments/registration.py`、`review_admin.py`、`teams_admin.py`、视图 |
| 06 内战 | `scrims/` 全部 |
| 07 战队与成员 | `teams/`、`members/` |
| 08 字体、预渲染、Caddy | `core/fonts/`、`core/prerender*.py`、`deploy/Caddyfile` |
| 09 运维 | 备份恢复、清理、worker、健康检查、邮件、信、发信（`core/` 相关） |
| 10 账号 | `accounts/`、allauth 适配、权限、注销导出、日历 |
| 11 后台 | `backoffice/` 全部、`core/autosave.py` |
| 12 前端脚本与模板 | `static/js/`、模板的 XSS、CSP |
| 13 搜索、首页、性能 | `search/`、`content/home.py`、`core/agenda.py`、sitemap、N+1 |
| 14 部署与 CI | `Dockerfile`、Compose、`scripts/`、`.github/`、`settings/prod.py` |
| 15 211–216 的改动 | `git diff 86cddb1..HEAD` 引入的回归 |
| 16 测试质量 | 绿了但没测到的测试、`mutate.py` 的覆盖 |

不做：任何修复（发现的问题留给 218 起的轮次）。

## 验收

- 16 份 `findings/*.md` 都有：每条问题写严重度（高 / 中 / 低）、位置（文件:行）、失败场景、怎么验证、是否已核对或已复现
- `review.md` 汇总去重、按严重度排、给出建议的修法顺序；和 210 已修的不重复
- 一个提交（只有 `handoff/` 下的文件），推送
