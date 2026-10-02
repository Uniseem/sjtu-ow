# 092 实现报告

## 结论

完成。设计 v5.2：页面铺满窗口、卡片自动排列，看和操作的页面整块居中；新文件 `docs/design-details.md` 写下每一页、每个部件的细节和决定；个人资料加个人宣言、常用位置、公开段位；战队加缺的位置和退役成员；文章页是铺满页头的封面、目录、作者卡和上下篇；头像、队标改圆角方形，画在五张底图上，名片和战队卡图在上，页脚山脊，空状态配图。

## 逐条结果

1. **文档**：`docs/design-details.md`（12 节，每条「决定」加理由，含用户原话）；`docs/design.md` 文档头 v5.2、13.2 约束后 v5.2 一段（指向细节文档）、3.5.1、3.8、5.2 文章页、5.5.1、6.1、6.3、7.1、7.2、7.4、7.6、12.3.1、12.6（新 12.6.4 `TeamAlumnus`）、12.7.2、13.2.4、13.2.5（「底图」）、13.2.6（`c-avatar`、`c-play`、`c-person`、`c-roster`、`c-teams`、`c-squad` / `c-alumni`、`c-cover`、`c-reading` / `c-toc` / `c-author` / `c-sequel`、`c-empty`、`c-masthead`）、13.13.4、附录 B（`motto`）、附录 D
2. **全宽**：`--container-page` 76rem → 120rem，桌面留白 40px；图片卡 `repeat(auto-fill, minmax(min(100%, 22rem), 1fr))`，名片 12rem（手机一行两张），战队卡 15rem，成员小卡 16rem；详情页 `l-split` 1536px 起侧栏 24rem；`l-container--narrow`（80rem）用在 13 个模板（赛事详情 / 报名 / 个人报名 / 报名详情、内战详情 / 列表、战队详情 / 申请 / 创建 / 管理、个人中心、搜索、登录注册）；页头 1280px 起中间是搜索框（窄了是放大镜）
3. **首页**：首屏 `c-hero__copy` 在左半边居中，标题 `clamp(4.25rem, 5.2vw, 6.25rem)`，校徽最大 48rem；数字四格居中；「近期」内战列表拉到和大图卡等高；战队用和战队列表同一个卡片组件
4. **个人资料**：`User.motto`、`main_role`、`flex_roles`、`show_rank`（`accounts/0005`）；`accounts/roles.py`：位置顺序、`best_ranks()`（每个位置在所有游戏 ID 里取最高，180 天算旧）、`public_profile()`；表单：宣言压成一行、拒绝 `http:`、`www.`、常见域名后缀，主位置从也能打里去掉；`components/play_style.html` 统一显示位置与段位（三个都选写「全能」）；`initial` 过滤器跳过开头的符号和表情
5. **宣言审核**：新送审类型 `motto`（`moderation/0004`，附录 B 同步）；保存用户时和昵称一起送审，空的不送；`moderate_scan` 也扫宣言；复核详情页对宣言条目多一个「同时清空这条个人宣言」勾选（宣言没有别的编辑入口），清空后刷新相关页面
6. **刷新**：用户的昵称、宣言、位置、公开开关变了，或公开段位的人改了段位，按原来的「昵称变了」那套刷新成员页、战队主页、内战、赛事、文章（`accounts/signals.py`）
7. **成员页**：名片 `c-person` 上半部正方形底图 + 大首字，下面昵称、这个组的职务（`split_titles()` 按顿号等拆开，最多 3 个 +N）、宣言、位置与段位、战队（最多 2 支，「等 N 支战队」）；分组宽屏左右两栏；全部成员小卡：头像、昵称、主位置和段位、所有职务（没有职务写分组名）；后台职务说明改成「多个职务用顿号分开，每个最多 10 字」并校验（`members/0002`）
8. **战队**：`Team.recruiting_roles` 和新表 `TeamAlumnus`（`teams/0003`）；退出、移除时 `_retire()`，通过申请 / 指定队长时 `_unretire()`，注销时 `leave_all_teams()` 一起删；`remove_alumnus()` 只许本人、队长、超级管理员；新地址 `teams/<pk>/alumni/<id>/remove/`；战队卡图在上（底图上放队标或首字，队标铺满）、「N / 上限 人 · YYYY.MM 成立」、简介两行、招募中加「缺 坦克、支援」；主页队头用底图横幅，现役成员卡，退役一行一个（12 人以上收起），侧栏加缺的位置和退役人数；管理页「退役成员」表写离队方式；「我的战队」列出自己的退役记录
9. **文章**：`content/article_meta.py`：字数（汉字 + 英文单词）、阅读时间（400 字 / 分钟，图片 10 秒、视频 1 分钟）、标题锚点 `h-1…`；页面：`c-cover` 封面（封面或占位图，上下两层黑色压层，面包屑、分类、标题、摘要、信息小块，下沿 `border-radius: 0 0 50% 50% / 0 0 2.5rem 2.5rem`）；正文 44rem 居中两端对齐、二级标题橙色竖条；3 个以上小标题有目录（窄屏折叠、1280px 起右侧粘住）；作者卡、上一篇 / 下一篇（同一栏目按发布时间）；文章卡加作者和「约 N 分钟」，图片换成 960×540
10. **插画风格**：`core/placeholders.py` 加五张静态底图（`HUE_SCENES`，用已有场景函数换配色，`still=True` 去掉动画）和页脚山脊（`render_ridge()`，三层，颜色是三个 night 令牌）；`render_placeholders` 写 48 张；`.c-hue-1` … `.c-hue-5` 背景是底图、加载前是对应的标签色；页脚 `::before` 是山脊；`c-empty::before` 一张小风景；头像圆角 8px（小的 4px），队标圆角方形
11. **其他**：导出个人信息加宣言、位置、开关、退役记录；隐私政策草稿（`content/legal/privacy.md`）写明段位默认公开可关、宣言和位置公开、退役记录可去掉、宣言送审；README 成员、战队、导出几段；AGENTS 读文档顺序加细节文档、新坑「Git Bash 的 heredoc 会吃掉一层反斜杠」
12. **本机演示数据**（不进仓库）：给演示用户随机填了宣言、位置、公开开关，补了一些段位、几条过期段位，「社长」改成「社长、主播」，几支队加缺的位置，前两支队加了退役记录；本机库跑了迁移和 `load_legal_pages --force`

## 验收输出

整组检查（Windows 本机，`PYTHONUTF8=1`，提交前最后一次）：

```
All checks passed!
261 files already formatted
No changes detected
System check identified no issues (0 silenced).
```

```
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1097 passed in 180.11s (0:03:00)
```

（1097 = 091 的 1041 + 本轮新加；新测试文件 `accounts/tests/test_public_profile.py`、`teams/tests/test_alumni_and_recruiting.py`、`members/tests/test_member_cards.py`、`content/tests/test_article_head.py`、`moderation/tests/test_motto.py`，以及占位图、设计体系里新加的几条。最后一组 `System check` 是 `check --deploy`，用 CI 的那组环境变量。）

前一次全量跑是 `1 failed, 1096 passed`：`test_body_text_rules_match_what_wagtail_renders` 读 `app.css` 找压缩写法，而跑测试期间重启了开发服务器，`tailwind runserver` 的监视进程把 `app.css` 换成了不压缩的版本（AGENTS 里 091 记的坑）。`tailwind build --force` 后重跑就是上面的 1097 passed。

变异（`handoff/rounds/092-design-details/mutate.py`，先跑基线）：

```
baseline green, 32 tests
caught the lowest rank wins -> test_each_position_shows_its_best_rank_over_every_game_id
caught ranks never go stale -> test_a_rank_older_than_180_days_is_marked_stale
caught the rank switch is ignored -> test_turning_the_switch_off_hides_every_rank_but_not_the_positions
caught the rank switch is ignored -> test_a_hidden_rank_stays_off_the_team_page
caught links allowed in the motto -> test_the_profile_form_keeps_the_motto_on_one_line_without_links
caught the main position repeats as flex -> test_the_main_position_is_not_repeated_as_a_flex_one
caught initials take any first character -> test_initials_skip_symbols_and_take_a_letter_or_a_character
caught leaving leaves no record -> test_leaving_and_being_removed_are_recorded_as_alumni
caught rejoining keeps the record -> test_coming_back_takes_the_person_off_the_alumni
caught account deletion keeps alumni -> test_deleting_an_account_takes_its_alumni_records
caught anyone may take a record off -> test_only_the_person_or_the_captain_can_take_a_record_off
caught the public page says how they left -> test_the_team_page_lists_the_roster_and_the_alumni_with_their_months
caught short positions shown while not recruiting -> test_short_positions_show_only_while_recruiting
caught one field, one post -> test_one_field_can_hold_several_posts
caught posts of any length -> test_each_post_is_ten_characters_at_most
caught every post listed -> test_more_than_three_posts_and_two_teams_are_counted_not_listed
caught group names over posts -> test_the_roster_card_shows_posts_across_groups
caught picture after the words -> test_a_card_shows_its_groups_posts_motto_play_and_teams
caught punctuation counted as words -> test_words_count_chinese_characters_and_latin_words
caught a slower reader -> test_reading_time_is_400_a_minute_plus_pictures_and_videos
caught contents from two headings -> test_contents_appear_from_three_headings
caught any edit counts as updated -> test_an_edit_a_day_later_is_shown_as_updated
caught mottos skip review -> test_a_motto_goes_to_review_and_an_empty_one_does_not
caught the clear box does nothing -> test_a_reviewer_can_clear_a_motto_and_nothing_else
caught a motto change regenerates nothing -> test_changing_what_the_cards_print_regenerates_the_member_page
caught private ranks regenerate pages -> test_a_new_rank_regenerates_the_pages_unless_it_is_private
caught the export forgets the motto -> test_the_export_carries_the_profile_and_the_alumni_records
caught a base picture missing from its class -> test_the_stylesheet_puts_each_base_picture_on_its_class
caught the front ridge is not the footer's ground -> test_the_footer_ridge_is_drawn_in_the_night_colours
caught a detail page goes full width again -> test_pages_to_read_and_act_on_sit_in_a_centred_column[tournaments/templates/tournaments/detail.html]
caught the centred column as wide as the page -> test_pages_to_read_and_act_on_sit_in_a_centred_column[scrims/templates/scrims/detail.html]
caught the team banner without its picture -> test_team_cards_lead_with_the_picture
restored and green; missed: none
```

31 处变异、32 项检查全部被抓到。

截图（无头 Edge，本机开发服务器 + 演示数据）：首页、成员（浅色、深色、390px）、战队列表、战队主页、文章、赛事详情和内战列表，1440 和 2000 宽，逐张看过。个人中心「基本资料」表单只有测试覆盖，没截图。

## 设计偏差

无。中途调整都先改了文档：队标从「缩到 84% 放在底图上」改成「铺满」（演示队标是方形不透明的，缩小后像加了一圈框）；内战详情不加段位；正文栏是 44rem（细节文档初稿写成 46rem，已改）。

## 未完成 / 顺带发现 / 需要确认

- **需要确认**：段位默认公开。用户问「段位怎么放」，我理解为要展示；隐私政策草稿已经写上「默认公开，可以关」。如果社团希望默认不公开，改 `User.show_rank` 的默认值和两处文档
- **未验证**：成员页一次画几十张底图（静态 SVG，同一张文件反复用）在低端手机上的流畅度
- **已知限制**：092 之前离队的人没有退役记录（以前离队直接删记录）
- **顺带发现**：开发服务器在本机改 Python 文件后又退出了两次，按 AGENTS 的做法重启
- **顺带发现**：Bash 工具里用 heredoc 跑内联 Python 时，反斜杠会少一层，几次把测试文件写坏，写进了 AGENTS 的坑

## 改动文件

- 文档：`docs/design-details.md`（新）、`docs/design.md`、`README.md`、`AGENTS.md`、`content/legal/privacy.md`、`handoff/STATUS.md`、本目录
- 模型和迁移：`accounts/models.py`、`accounts/migrations/0005_user_public_profile.py`、`teams/models.py`、`teams/migrations/0003_team_alumni_and_recruiting_roles.py`、`members/models.py`、`members/migrations/0002_title_help.py`、`moderation/models.py`、`moderation/migrations/0004_alter_moderationitem_target_type.py`
- 代码：`accounts/roles.py`（新）、`accounts/forms.py`、`accounts/services.py`、`accounts/signals.py`、`teams/services.py`、`teams/forms.py`、`teams/views.py`、`teams/urls.py`、`members/services.py`、`moderation/admin_views.py`、`moderation/integrations.py`、`moderation/services.py`、`moderation/signals.py`、`moderation/management/commands/moderate_scan.py`、`content/article_meta.py`（新）、`content/models.py`、`content/home.py`、`core/placeholders.py`、`core/templatetags/ow.py`
- 样式和模板：`assets/css/input.css`、`templates/base.html`、`templates/components/{icon,post_card,team_tile,tournament_card,empty_state,play_style}.html`、`templates/me/{base,teams}.html`、`templates/account/layout.html`、`content/templates/content/{article_page,home_page,_toc}.html`、`members/templates/members/index.html`、`teams/templates/teams/{detail,index,manage,apply,create,_alumnus}.html`、`tournaments/templates/tournaments/{detail,register,individual_signup,registration_detail}.html`、`scrims/templates/scrims/{detail,index}.html`、`search/templates/search/results.html`、`moderation/templates/moderation/detail.html`
- 生成的文件：`static/img/placeholders/hue-1.svg` … `hue-5.svg`、`ridge.svg`（新）
- 测试：上面五个新文件；`content/tests/test_editorial_pages.py`、`content/tests/test_home_sections.py`、`core/tests/test_arena_v3.py`、`core/tests/test_chapter15_audit.py`、`core/tests/test_colour_modes.py`、`core/tests/test_cover_placeholders.py`、`core/tests/test_design_system.py`
