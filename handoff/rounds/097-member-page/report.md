# 097 实现报告

## 结论

完成。成员有了个人主页 `/members/<编号>/`（基础版），各处的成员名字都能点进去。页面设计待和用户讨论。

## 逐条结果

1. **地址和权限**：`members/urls.py` 加 `members/<int:pk>/`（`member_detail`）；`members/views.py` 的 `member_detail` 只认 `joined_users()` 里的人，其他 404
2. **内容**：`members/services.py` 的 `member_page()` 返回 `MemberPage`：`public_profile`（位置、段位，尊重「公开段位」）、可见分组和每组职务（`split_titles`）、现役战队（未解散，带人数）、退役记录（未解散的队，按离队时间倒序）、发表的文章（已发布、公开，最新 10 篇和总数）；`member_url()`
3. **模板** `members/templates/members/detail.html`：居中窄栏；页头是面包屑、88px 底图头像、昵称、宣言、位置段位、分组职务标签；下面「所在战队」（战队卡）、「待过的战队」（行：队名、起止年月，不写离队方式）、「发表的文章」（行：日期块、标题）；`extra_head` 里 `noindex`
4. **链接**：模板过滤器 `member_url`（停用的人返回空，模板就只写名字）；成员展示页的名片名字和小卡名字改成撑满整卡的链接（`c-stretch`），名片里的战队名浮在上面；战队主页现役成员卡、退役列表、文章作者卡；站内搜索的成员结果链到个人主页、摘要是宣言。样式：`.c-person`、`.c-roster__item`、`.c-squad__item` 加 `position: relative`，悬停时名字变色
5. **文档**：设计 v5.5（6.3、6.4、附录 D），细节 1.6、4.6，README
6. **测试**：新文件 `members/tests/test_member_page.py`（10 条）；`search/tests/test_search.py` 成员结果的地址、`teams/tests/test_alumni_and_recruiting.py` 退役名字后面的标签按新行为改

## 验收输出

（Windows 本机，`PYTHONUTF8=1`，`main`）

```
All checks passed!
266 files already formatted
No changes detected
System check identified no issues (0 silenced).
```

```
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1201 passed in 124.04s (0:02:04)
```

（1201 = 094 的 1191 + 10。前一次全量 `1 failed, 1200 passed`，失败的是读 `app.css` 的 `test_body_text_rules_match_what_wagtail_renders`：开发服务器的监视进程在测试期间把 `app.css` 换成了不压缩版。停掉开发服务器、`tailwind build --force` 后重跑就是上面的结果。）

变异（`handoff/rounds/097-member-page/mutate.py`）：

```
baseline green, 9 tests
caught anyone gets a page -> test_only_the_people_on_the_showcase_have_a_page
caught search engines may index it -> test_the_page_stays_out_of_search_engines
caught the game ID is shown -> test_the_page_shows_what_is_public_and_nothing_else
caught the teams left are dropped -> test_current_teams_and_the_ones_left
caught how they left is public -> test_current_teams_and_the_ones_left
caught drafts are listed -> test_the_articles_they_wrote
caught a card opens nothing -> test_every_card_on_the_showcase_opens_the_page
caught the byline is plain text -> test_the_team_page_and_the_byline_lead_to_it
caught the deactivated are linked -> test_someone_without_a_page_is_not_linked
caught search sends members to the list -> test_members_are_the_people_on_the_members_page
restored and green; missed: none
```

10 处变异全部被抓到。

截图：在试验分支合并 `main` 之后截（用户本地看的是试验分支），见合并说明。

## 设计偏差

无。

## 未完成 / 顺带发现 / 需要确认

- **需要确认**：页面放什么、长什么样、要不要被搜索引擎收录、要不要预渲染（用户说后面讨论）
- **未做**：预渲染（实时渲染）；参赛和内战记录
