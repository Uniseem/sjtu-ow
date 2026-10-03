# 127 已发布的文章也能一键通知全体成员（报告）

## 做了什么

1. `core/models.py`：`Broadcast.Kind` 加 `ARTICLE`（「新文章」），迁移 `core/0017` 只改 choices
2. `content/notifications.py`（新）：`new_article_letter()`，主题「分类名：标题」，没有分类写「文章」；摘要做正文，按钮「阅读全文」指向文章地址，带退订
3. `core/services.py`：`Kind` 多了 `is_live`（只有已发布的能发）、`back_url`（发完回哪）、`label`（面包屑）；`announcement_problem()` 改用 `is_live` 判断。文章这一类：内容编辑、认证作者能发（`user_can_edit_author`）（**130 轮更正**：`user_can_edit_author` 只认超级管理员和内容编辑，认证作者不能发；设计 10.4 写的也是「内容编辑（含超级管理员）」，代码和设计一致，是这里写错了），已发布的才能发，发完回到文章所在的页面列表
4. `core/announce_admin.py`：去掉自己维护的「回哪」表，统一从 `kinds()` 取
5. `content/wagtail_hooks.py`：页面列表的「更多」和编辑页顶部菜单加「通知全体成员」（`AnnounceArticleItem`），已发布、有权限、没发过才出现
6. 邮件样张页加「新文章通知（群发）」
7. 设计 v6.23：10.4 的「通知全体成员」加文章、10.2 表加一行、10.3 主题写法，附录 D

## 命令输出

变异（`mutate.py`，10 处，第一次全部被抓到）：

```
baseline green, 3 tests
caught drafts count as published -> test_drafts_and_other_roles_cannot_announce_articles
caught any admin user may announce articles -> test_drafts_and_other_roles_cannot_announce_articles
caught the menu item shows on drafts -> test_drafts_and_other_roles_cannot_announce_articles
caught the menu item shows to everyone -> test_drafts_and_other_roles_cannot_announce_articles
caught the menu item stays after sending -> test_content_editors_announce_an_article
caught no item in the page list -> test_content_editors_announce_an_article
caught no item on the edit page -> test_content_editors_announce_an_article
caught the subject ignores the category -> test_content_editors_announce_an_article
caught the letter has no summary -> test_content_editors_announce_an_article
caught no specimen -> test_both_notices_are_on_the_specimen_page
restored and green; missed: none
```

整组检查（本机）：

```
1483 passed in 320.62s (0:05:20)
No changes detected
System check identified no issues (0 silenced).
All checks passed!
304 files already formatted
```

演示站升级：

```
  Applying core.0017_alter_broadcast_kind... OK
全量生成完成：成功 46，失败 0，删除 0；目录占用 1606 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

## 没做 / 未验证

- 发布文章时没有「同时通知」的勾选：文章发布要走审核和定时发布，在 Wagtail 的发布流程里插一步确认会和它们打架。发布后在列表里点一下就行
- 演示站没配 SMTP，没有真的发出去（预览页会提示没配邮件）
- 部署时文件清单没传上去，`deploy_ship.sh` 里去掉 CRLF 那步跳过了，补传后重跑了一遍；Python 读 CRLF 不受影响，提交推送后服务器用 `git pull` 对齐
