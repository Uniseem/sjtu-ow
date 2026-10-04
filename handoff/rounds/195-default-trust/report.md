# 195 默认信任（报告）

## 做了什么

1. **头像上传即生效**：
   - `submit_avatar` 处理完直接建「已通过」的记录（没有审核人、记上时间），换上新头像（经 `save()`，显示它的页面重新生成），删掉本人上一张上传的
   - 去掉 `pending_avatar`、`withdraw_avatar`、`approve_avatar`、`reject_avatar`，待审头像的提醒信和它的任务（`accounts/tasks.py` 整个删了）、「头像未通过」信，个人中心的「审核中」「撤回」和撤回地址
   - 后台「审核 → 头像」改叫「头像」，默认列出在用的、最新的在前，只留「撤下」（照旧选原因、发信）
   - 首页待办和审核标签不再数头像
   - 迁移 `accounts/0009`：升级时还在审核中的头像直接换上
2. **投稿直接发布**：
   - `assign_content_permissions` 给投稿者组在文章栏目上加「发布」
   - `content.services.retire_content_workflow()`：把「内容审核」工作流从文章栏目解绑，工作流和步骤停用（记录留着），正在审核中的取消；`init_site` 不再建它，改成调这个
   - 迁移 `content/0008`：对现有库做同样的事，并补上发布权限
   - 去掉审核标签的「稿件」、首页「N 篇稿件等待审核」、「我的投稿」里的「审核中 / 需修改」
3. **只能发布、撤下自己的文章**：`content.permissions.OwnArticlesPermissionTester`。`ArticlePage.permissions_for_user` 返回它，内容编辑和超级管理员以外的人只能对自己的文章 `can_publish` / `can_unpublish`。Wagtail 的撤下视图、批量操作都走 `permissions_for_user`，普通 `Page` 实例也会转成文章再问，所以网址直接访问也拦得住。以前认证作者能撤下别人的文章，这次一起堵上了
4. `submits_for_review` 改名 `plain_writer`（编辑页的投稿须知和去掉「推荐」标签页还按它判断）
5. 文字改了：投稿须知、`/submit/`、头像上传说明、后台头像页、后台手册（内容编辑那几步）、上线清单里内容编辑那项、用户协议草稿第三节第 4 条；邮件样张页去掉三封不再发的
6. 设计 4.1、5.4、5.5.1、10 章两张表、14.1、14.3、19 章，细节 2.3，附录 D v6.73；README 新一节「默认信任」，改了 `init_site` 的说明和头像一段，删掉一句 117 时的旧菜单
7. **测试机走端口转发**（用户 10-05 本轮中途：「测试机因为是 v6 连不上，所以我改用另一台机进行了端口转发。使用 189.24.110.12:2222 可进行 ssh 连接，你试试，并且写到 agents.MD 里」）：
   - 连上了，经转发拿到的 ED25519 主机指纹和以前直连 IPv6 时记下的一样，是同一台
   - 本机 `~/.ssh/config` 的别名 `sjtu-ow-test` 改成走 `189.24.110.12:2222`，加 `HostKeyAlias`；原文件备份成 `config.bak-20261005`，直连 IPv6 的那条留着
   - `scripts/remote-check.sh` 默认连 `sjtu-ow-test`
   - AGENTS.md 写了转发、配置写法、指纹，以及「那台机器的 22 端口不是我们的」

## 命令输出

变异（本机，15 处，全部被抓到）：

```
baseline green, 8 tests
caught uploads wait again -> test_an_upload_shows_at_once
caught the face not put up -> test_an_upload_shows_at_once
caught the face not put up -> test_a_new_upload_replaces_the_face_and_deletes_the_old_upload
caught old uploads kept -> test_a_new_upload_replaces_the_face_and_deletes_the_old_upload
caught anyone takes down anyone's -> test_nobody_takes_down_someone_elses_article_but_editors
caught articles use Wagtail's own tester -> test_nobody_takes_down_someone_elses_article_but_editors
caught members may not publish -> test_members_publish_their_own_articles_straight_away
caught the workflow stays on the section -> test_init_site_retires_the_review_workflow_left_from_before
caught reviews left running -> test_init_site_retires_the_review_workflow_left_from_before
caught init_site leaves the workflow -> test_init_site_retires_the_review_workflow_left_from_before
caught oldest faces first -> test_the_page_lists_the_faces_in_use_newest_first
caught the guide still says review -> test_submitters_get_the_guide_and_editors_do_not
caught the form still says review -> test_an_upload_shows_at_once
caught migration keeps the workflow bound -> test_waiting_faces_go_up_and_reviews_end
caught migration leaves reviews running -> test_waiting_faces_go_up_and_reviews_end
caught migration leaves waiting faces down -> test_waiting_faces_go_up_and_reviews_end
restored and green; missed: none
```

本机第一次全量红了一条（`test_forms_that_take_something_away_ask_first[templates/me/profile.html-me_avatar_withdraw]`，列表里还写着删掉的撤回表单），去掉那一项后：

```
1747 passed, 1 skipped in 249.64s (0:04:09)
```

测试机（184 以来第一次连上，走转发）整组 `bash scripts/remote-check.sh`：

```
== ruff (17:32:18)
All checks passed!
== pytest (17:32:19)
分片 1：437 passed in 55.85s
分片 2：437 passed in 62.28s (0:01:02)
分片 3：437 passed in 56.85s
分片 4：437 passed in 62.67s (0:01:02)
== 迁移 (17:33:29)
No changes detected
== 生产配置 (17:33:30)
System check identified no issues (0 silenced).
== 错误页和模板一致 (17:33:31)
== Docker 镜像 (17:33:33)
构建成功：e764483558c6
== 全部通过 (17:33:33)
```

### 正式站

升级前备份 `sjtu-ow-20261005-013416.tar.gz`（210.2 MB）。`deploy_ship.sh 195`：

```
 Image sjtu-ow-web Built 
 Image sjtu-ow-worker Built 
sjtu-ow-web 2026-10-04 19:34:30 +0200 CEST
  Applying content.0008_publish_without_review... OK
 Container sjtu-ow-worker-1 Starting 
 Container sjtu-ow-worker-1 Started 
全量生成完成：成功 12，失败 0，删除 0；目录占用 280 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

升级前先核过：正式站的用户协议、隐私政策和旧草稿渲染出来的文字完全一样（`terms SAME`、`privacy SAME`），没人改过。所以升级后用 `load_legal_pages --force` 重新导入，再全量预渲染：

```
migrations True True
workflow bound False active workflows []
submitters publish True
pending avatars 0
已发布「用户协议」
已发布「隐私政策」
terms says True False True
全量生成完成：成功 12，失败 0，删除 0；目录占用 280 KB
```

公开的 `/terms/` 里能找到「投稿发布后立即公开」（`grep -c` 为 1）。

## 没做 / 顺带发现

- 头像没有自动检查（AI 只看文字），见复核
- `content/notifications.py` 里给作者的「审核通过 / 退回」代码没删（不会再触发），后台重写时一起清
- 认证作者只剩「推荐」标签页的区别
