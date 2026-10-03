# 124 新成员上手（报告）

## 怎么查的

本机空库，`scratchpad/walk_member.py` 以新成员身份：注册（邮件发到内存里读验证码）、确认，再打开个人中心、游戏 ID 页、战队页、申请页、赛事页、个人报名页、内战页、成员展示、投稿入口；另以投稿者身份打开新建稿件页看按钮和字段（`walk_submitter.py`）。能走通，卡顿的三处见请求。

## 做了什么

1. **落地页**：`AccountAdapter.get_signup_redirect_url()` 返回个人中心「基本资料」，并加一条欢迎（补全游戏 ID 和联系方式就能报名赛事、内战，也可以去「战队」找队伍）。allauth 只在没有 `next` 时用它，所以从别的页面带着 `next` 来注册的人照旧回去；它在确认码之后才调用，确认码页上不会提前出现欢迎
2. **去补全**：赛事页的「暂时不能个人报名」下面加 `profile_gap_links`（`tournaments/slots.py` 在有问题时给出缺的项）；战队页「请先在个人中心添加至少一个游戏 ID」后面加链接（`teams.slots.join_gaps()`，整页和片段共用；`teams.services.lacks_game_account()` 也给 `can_apply` 用）
3. **投稿须知**：`content/panels.py` 的 `SubmissionGuidePanel`（文章编辑页最上面，在「AI 审核」后面），只给 `content.permissions.submits_for_review()` 为真的人：不是超级管理员、内容编辑、认证作者的。内容照编辑页上的实际按钮写：「保存草稿」「更多动作 → 提交给内容审核」，正文的「+」能加段落、图片、引用、B 站视频，「推广」「设置」不用管
4. **文档**：设计 v6.20（3.1、5.4.3）

## 命令输出

变异（`mutate.py`，9 处，第一次全部被抓到）：

```
baseline green, 4 tests
caught new members land on the homepage -> test_a_new_member_lands_on_their_profile_with_what_to_do
caught no welcome -> test_a_new_member_lands_on_their_profile_with_what_to_do
caught the tournament notice has no links -> test_the_tournament_notice_links_to_what_is_missing
caught the tournament slot computes no gaps -> test_the_tournament_notice_links_to_what_is_missing
caught the team notice has no link -> test_the_team_notice_links_to_adding_a_game_id
caught the team page passes no gaps -> test_the_team_notice_links_to_adding_a_game_id
caught the team fragment passes no gaps -> test_the_team_notice_links_to_adding_a_game_id
caught nobody gets the guide -> test_submitters_get_the_guide_and_editors_do_not
caught editors get the guide too -> test_submitters_get_the_guide_and_editors_do_not
restored and green; missed: none
```

整组检查：

```
All checks passed!
301 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
1472 passed in 187.55s (0:03:07)
```

## 没做 / 未验证

- 投稿须知没有截图看排版（Wagtail 的 `help-block help-info` 样式）
- 「推广」「设置」两页没有对投稿者隐藏：Wagtail 的标签页由面板定义，隐藏要拆开两套面板，这轮只说明

演示站：镜像时间 `2026-10-03 19:59:22 +0200`，「No migrations to apply.」，全量生成「成功 46，失败 0」，健康检查 ok。
