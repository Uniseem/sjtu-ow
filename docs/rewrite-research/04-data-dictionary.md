# 04 · 完整数据字典与迁移处置

来源：第二轮数据字典代理。生产 schema 以「全部迁移渲染后的最终模型状态」为准（django 6.0.8、wagtail 8.0、django-allauth 65.19.3、django-tasks-db 0.13.0、treebeard 5.3.1）。`data/db.sqlite3` 是落后进度的 dev 快照，里面的 `lfg_lfgpost`、`core_gamemode`、`integrations_*` 在最终 schema 已删除，不能当生产表清单。

**SQLite 存储格式（Go 导入器）**：布尔存 0/1；DateTimeField 存 UTC 无时区文本 `YYYY-MM-DD HH:MM:SS.ffffff`；JSONField/TextField 均 TEXT；UUIDField 存 32 位 hex。

## 一、自有表逐字段

### 1. accounts

**accounts_user**（BigAutoField 主键）：id PK；password Char(128)（Argon2 优先、PBKDF2 兜底）；last_login null；is_superuser bool；first_name/last_name Char(150)（遗留未用）；is_staff bool；is_active bool；date_joined；**email Email(254) unique**（登录标识）；nickname Char(16)（最少 2 字）；is_sjtu bool；sjtu_verified_via Char(32) null；sjtu_verified_at null；agreed_terms_at NOT NULL；agreed_cross_border_at NOT NULL；deactivation_note Char(200) ''；motto Char(30) ''；main_role Char(8)（tank/damage/support）''；flex_roles Char(32) CSV；show_rank bool True；accepts_announcements bool True；calendar_version PositiveInt 0；avatar_id FK→wagtailimages.Image SET_NULL。
- M2M 副表：accounts_user_groups、accounts_user_user_permissions。
- 约束：`Lower(email)` CI 唯一（accounts_user_email_ci_unique）。

**accounts_avatarsubmission**：user_id FK CASCADE；image_id FK SET_NULL；status Char(16)（pending/approved/rejected/withdrawn/taken_down）default pending；reason Char(32)（moderation.Category）''；note Char(200) ''；reviewed_by_id FK SET_NULL；reviewed_at null；created_at。约束：每人至多一条 pending（条件唯一）。

**accounts_gameaccount**：user_id FK CASCADE；battletag Char(64)（「名称#数字」）；rank_tank/rank_damage/rank_support SmallInt null（**有符号**；0–39=段位编码、40=前 500、NULL=未定级，见 accounts/ranks.py）；ranks_updated_at（save 自动刷新）。约束：`Lower(battletag)` CI 全局唯一。

**accounts_contactmethod**：user_id FK CASCADE；type Char(16)（qq/wechat/phone/other）；value Char(64)。约束：(user,type) 唯一。

**accounts_featuregrouprestriction**：group_id FK→auth_group CASCADE；feature Char(32)（7 种）；note Char(200)；updated_by_id FK SET_NULL。约束：(group,feature) 唯一。

**accounts_featureuserrule**：user_id FK CASCADE；feature 同上；allowed bool False；note；updated_by_id。约束：(user,feature) 唯一。

### 2. content（四个 Page 子类为 MTI，主键即 wagtailcore_page.id）

**content_articlecategory**：name Char(32) ''；slug Slug(64) ''；sort_order PositiveInt 0；allow_submission bool True。约束：slug≠"" 时唯一。

**content_homepage**：仅 page_ptr_id OTO→wagtailcore.Page；max_count=1。

**content_homepagepinnedarticle**：sort_order Int null；page_id ParentalKey CASCADE；article_id FK CASCADE。约束：(page,article) 唯一（≤3 篇是应用层校验）。

**content_articleindexpage**：page_ptr_id；intro Text ''（Markdown）。

**content_articlepage**：page_ptr_id；category_id FK PROTECT null（列 NOT NULL 但允许迁移期空）；cover_id FK SET_NULL；summary Char(200) ''；body Text ''（Markdown）；body_plain Text ''；body_words PositiveInt 0；body_minutes PositiveInt 1；author_id FK User PROTECT NOT NULL；comments_enabled bool True；tournament_id FK SET_NULL。

**content_standardpage**：page_ptr_id；body Text ''（Markdown）。

### 3. core

**core_healthprobe**：token Char(32)。（探针行写入后回滚，恒空。）

**core_sitesettings**（单例，仅一行 id=1）。按后台分组：
- 邮件发送：smtp_host Char(255) ''；smtp_port PositiveInt 465；smtp_security Char(16)（none/starttls/ssl）default ssl；smtp_username Char(255) ''；**smtp_password EncryptedTextField ''**；from_address Email(254) ''；from_name Char(100) 'SJTU-OW'；email_subject_prefix Char(40) '[SJTU-OW]'。
- 站点信息：site_description Text ''；default_share_image_id FK SET_NULL；hero_image_id FK SET_NULL；founded_on Date null；qq_group_url URL(200) ''（必须 https）。
- 栏目横幅：banner_news_id / banner_tournaments_id / banner_scrims_id / banner_teams_id / banner_members_id 五个 FK SET_NULL。
- 社区参数：team_max_members 10；team_max_captained 3；max_game_accounts 5；scrim_reminder_hours 2；tournament_reminder_hours 24。
- AI 审核：moderation_enabled True；moderation_model 'deepseek-v4.1-flash'；moderation_daily_limit 2000；moderation_image_enabled False；moderation_alert_email ''；**moderation_api_key 加密 ''**；moderation_base_url URL ''；moderation_extra_body JSON dict；moderation_timeout 30；moderation_max_output_tokens 600。
- 异地备份：backup_s3_enabled False；backup_s3_endpoint URL ''；backup_s3_bucket Char(64) ''；backup_s3_region 'auto'；backup_s3_access_key_id Char(128) ''；**backup_s3_secret_access_key 加密 ''**；backup_s3_prefix 'sjtu-ow/'。
- 排版：font_css_path Char(500) ''；font_css_generated_at null。

加密字段为 Fernet 密文（base64，`gAAAA…` 开头），密钥环境变量 FIELD_ENCRYPTION_KEY；空值存 ''；导入器要么原样搬密文+保留密钥，要么解密重加密。

**core_fontfamily**：name Char(64)；css_name Char(32) unique（自动分配 sjtu-font-<n>）；source Char(16)（upload/google_fonts/url）；source_ref Char(500)；license_type Char(16)（open_source/web_license/other）；license_note Text；license_confirmed bool；created_by_id FK SET_NULL；created_at。

**core_fontface**：family_id FK CASCADE；weight PositiveSmallInt 100–900（100 步进）；style Char(8)（normal/italic）；original_file FileField(500)（路径 fonts/<family_id>/original/<file>）；status Char(16)（pending/processing/ready/failed）；progress 0；error Text；slices JSON list；slice_count/total_bytes/glyph_count PositiveInt；created_at/updated_at。约束：(family,weight,style) 唯一。

**core_typographyrule**：region Char(16) unique（body/h1/h2/h3/h4/nav/button/numeric/mono，固定 9 行）；mode（system/inherit/custom）default inherit；family_id FK PROTECT null；weight 400；size_rem Decimal(5,3) null；line_height Decimal(4,2) null；letter_spacing_em Decimal(5,3) null；updated_at。

**core_prerenderedpage**：path Char(500) unique；kind Char(32)（12 种）；status（pending/ready/failed）；requested_at/generated_at；content_hash Char(64)；bytes；error Text。（可整体再生。）

**core_broadcast**：kind Char(16)（tournament/scrim/article）；object_id PositiveInt（多态无 FK）；audience（everyone/participants）；before PositiveSmallInt；note Text；moved_from null；subject Char(200)；sent_by_id FK SET_NULL；recipient_count；waits_for_publish bool；created_at。索引 (kind,object_id)。

**core_heldletter**：batch UUID db_index；actor_id FK User CASCADE；letter JSON（完整信件）；recipients JSON（[[addr,name]…]）；back Char(500) ''；in_back_office bool；state（waiting/sent/skipped）；created_at；decided_at。

### 4. teams

**teams_team**：name Char(16)；description Text(500) ''；logo_id FK SET_NULL；is_recruiting True；recruiting_roles Char(32) CSV；member_contact Char(100)（仅队内可见）；disbanded_at null（软删）；created_at/updated_at。约束：`Lower(name)` 且未解散 CI 唯一（unique_active_team_name）。

**teams_teammembership**：team_id/user_id FK CASCADE；role Char(16)（captain/member）；joined_at。约束：(team,user) 唯一；每队至多一 captain（条件唯一）。

**teams_teamapplication**：team_id/applicant_id FK CASCADE；role_tank/damage/support bool；message Char(200)；status（pending/approved/rejected/cancelled）；decided_by_id FK SET_NULL；decided_at；decision_note Char(200)；captain_reminded_at；created_at。约束：每队每人一条 pending（条件唯一）。

**teams_teamalumnus**：team_id/user_id FK CASCADE；role（离队时身份）；joined_at/left_at NOT NULL；reason（left/removed）。约束：(team,user) 唯一。

### 5. members

**members_membergroup**：name Char(20) ''（空=不展示）；description Char(200)；is_visible True；sort_order。约束：非空名 CI 唯一。

**members_membergroupmembership**：sort_order Int null；group_id ParentalKey CASCADE；user_id FK CASCADE；title Char(20)（职务，每段 ≤10 字）。约束：(group,user) 唯一。

### 6. tournaments

**tournaments_tournament**：title Char(100)；summary Char(300)；description Text + description_plain；cover_id FK SET_NULL；starts_at null；registration_opens_at/closes_at null（发布必填）；roster_min 5 / roster_max 6；sjtu_only False；registration_mode（individual/team）default individual；auto_approve False；status（draft/published/finished/cancelled）；created_by_id FK SET_NULL；published_at；reminder_sent_at；moved_from；participant_contact Char(100)；created_at/updated_at。Check：`roster_min>=1 AND roster_max<=20 AND min<=max`；`registration_opens_at < registration_closes_at`（NULL 草稿天然通过）。

**tournaments_registration**：tournament_id FK CASCADE；team_id FK **PROTECT** null（NULL=临时队）；status（pending/approved/rejected/withdrawn）；team_name Char(16) 快照必填；roster_version 1；submitted_by_id FK SET_NULL；submitted_at；status_note Char(300)；created_at/updated_at。约束：(tournament,team) 唯一；team_name 非空 Check；索引 (tournament,status)、(updated_at,id)。

**tournaments_registrationmember**：registration_id/tournament_id FK CASCADE；user_id FK **PROTECT**；game_account_id FK SET_NULL；nickname/battletag 快照；is_sjtu；rank_* PositiveSmallInt null（**无符号**，与 GameAccount 的有符号不同）；is_captain；is_active True（占名额）。约束：每赛事每用户仅一条 active。

**tournaments_registrationstatuslog**（只增）：registration_id FK CASCADE；action Char(16)（submit/resubmit/sync_roster/approve/reject/revoke/withdraw/form_team/member_left/dissolve）；from_status/to_status；actor_type（captain/admin/system/member）；actor_user_id FK SET_NULL；roster_version；roster_snapshot JSON null；note Text；created_at。

**tournaments_individualsignup**：tournament_id/user_id FK CASCADE；game_account_id FK SET_NULL；role_* 三 bool；registration_id FK SET_NULL（编入临时队后回填）；created_at/updated_at。约束：(tournament,user) 唯一；至少一个位置 Check。

### 7. scrims

**scrims_scrim**：title Char(100)；description + description_plain；starts_at null（发布必填）；signup_closes_at null（空=开始前都可报）；format（rq_5v5/rq_6v6/open_5v5/open_6v6）default rq_5v5；sjtu_only；status；teams_generated_at；roster_changed_at（分队变动戳，与 updated_at 区分）；reminder_sent_at；moved_from；created_by_id FK SET_NULL；created_at/updated_at。索引 (status,starts_at)。

**scrims_scrimsignup**：scrim_id/user_id FK CASCADE；game_account_id FK SET_NULL；role_* 三 bool；is_selected False；team Char(1)（a/b，默认 ''）；assigned_role Char(8) 默认 ''；rating_used PositiveSmallInt null；created_at/updated_at。约束：(scrim,user) 唯一；至少一位置 Check。

### 8. moderation

**moderation_moderationitem**：target_type Char(32)（nickname/motto/team_name/team_description/application_message/article/tournament_description/scrim_description/page/image/comment）；target_id PositiveInt 0；field Char(32)；url Char(500)；author_id FK SET_NULL；excerpt Text；full_text Text；text_hash Char(64)；risk（none/low/medium/high/unknown）default unknown；categories JSON（illegal/porn/attack/politics/scam/game_trade/privacy/impersonation/other）；reason/quote Text；model Char(64)；input/output_tokens；status（pending/ok/handled/ignored）；reviewed_by_id/reviewed_at；handling_note Char(300)；checked_at/notified_at；attempts 0；last_error Char(300)；failed_at；created_at。约束：(target_type,target_id,field,text_hash) 唯一；索引 (status,risk,created_at)、(text_hash)。

**moderation_moderationusage**：date unique；calls/items/input_tokens/output_tokens。

### 9. comments

**comments_comment**：page_id FK→content_articlepage CASCADE；author_id FK **PROTECT**；parent_id FK self CASCADE（只指向顶层）；reply_to_user_id FK SET_NULL；body Text（≤500 校验层）；created_at；edited_at；is_pinned/is_hidden/is_deleted bool；like_count PositiveInt（冗余）。约束：每页至多一条置顶（条件唯一）；索引 (page,created_at)、(page,is_pinned,like_count)。

**comments_commentlike**：comment_id/user_id FK CASCADE；created_at。约束：(comment,user) 唯一。

### 迁移里才看得到的史实

- content/0007/0009/0012 三次**数据格式转换**：body/description 由 StreamField JSON → Markdown——**旧 revision 的 content JSON 里 body 可能仍是 StreamField 数组**（迁移只转当前值，历史 revision 原样留着）。
- core/0011：DROP lfg_lfgpost、删 GameMode；content/0006：停用 Wagtail 审核工作流（workflow/task 表只剩 active=0 死行）、root 改名。
- tournaments/0004/0005：删 integrations 上游外键（awaiting→pending）。
- 索引均为 Meta.indexes 所建，无隐藏 RunSQL 索引。

## 二、第三方表与处置

标记：**①导入器必须读**　**②可丢弃**（未使用/可再生）　**③暂不确定**

### wagtailcore（22 张 + 3 张 M2M）

| 表 | 处置 | 说明 |
|---|---|---|
| wagtailcore_page | **①** | 与 content_*page 四张子表合成新 pages/articles 表（见下节） |
| wagtailcore_revision | **①** | 全部草稿与发布历史；正文在 content JSON 里 |
| wagtailcore_site | **①**（仅 1 行） | 域名/端口/site_name/root_page_id，新系统站点配置种子 |
| wagtailcore_pagelogentry | ③ | 页面操作审计；新系统如保留操作史则读，否则弃 |
| wagtailcore_modellogentry | ③ | snippet（分类）等对象审计，同上 |
| wagtailcore_collection | ② | 只有 Root 一行（图片集合实际是 wagtailimages 里按 collection？——本项目实证：图片全部在根集合，"默认封面"等业务集合信息在集合名上，导入器需按集合名建新集合结构）|
| wagtailcore_referenceindex | ② | 引用索引，可再生 |
| wagtailcore_locale | ② | 仅一行 zh-hans，新系统单语言 |
| wagtailcore_uploadedfile | ② | 富文本拖拽临时文件，基本为空 |
| wagtailcore_comment/commentreply | ② | /wagtail/ 侧边批注，未用 |
| wagtailcore_workflow/task/workflowtask/taskstate/workflowstate/workflowpage/workflowcontenttype/groupapprovaltask（+ _groups） | ② | 0006 已整体退役（active=0 死行）|
| wagtailcore_grouppagepermission | ③ | 组的 Wagtail 页面权限；新后台权限体系重设计的话弃，保留组语义则作参考 |
| wagtailcore_pagesubscription | ② | 未用 |
| wagtailcore_pageviewrestriction/collectionviewrestriction（+ _groups） | ② | 私有页/集合，未用 |
| wagtailcore_groupcollectionpermission/groupsitepermission | ② | 未用（图片集合权限实际走这张——新系统重建权限模型时作参考）|
| wagtailcore_apitoken | ② | 未用 |

### wagtailimages / wagtailsearch / wagtailembeds / wagtaildocs

| 表 | 处置 | 说明 |
|---|---|---|
| wagtailimages_image | **①** | 全站图片库（头像、封面、横幅、队标）|
| wagtailimages_rendition | **①**（或②）| 缩略图行 + 磁盘文件一一对应（media/images）。保留现成文件则读；全部重生成也可弃，成本高 |
| wagtailsearch_indexentry（+ FTS5 虚拟表、影子表、3 个触发器） | ② | 数据库搜索索引，可由 body_plain/description_plain 重建 |
| wagtailembeds_embed | **①**（小；弃了也只损失 b23 缓存）| b23.tv 短链解析缓存 |
| wagtaildocs_document | ② | 文档库未用 |

### 其余 Wagtail 应用

| 表 | 处置 | 说明 |
|---|---|---|
| wagtailredirects_redirect | ③ | 改名页重定向（unique(old_path,site)）；生产若有行则搬进新重定向表 |
| wagtailforms_formsubmission | ② | 无 FormPage，0 行 |
| wagtailusers_userprofile | ② | 后台偏好，可再生 |
| wagtailadmin_admin / editingsession / formstate | ② | 标志表 / 编辑器会话（自动保存走 revision，不用它）|

### allauth / taggit / django-tasks / Django 内建

| 表 | 处置 | 说明 |
|---|---|---|
| account_emailaddress | **①** | 邮箱验证状态（verified/primary）是账号体系核心 |
| account_emailconfirmation | **①→②** | 验证码/确认 key；迁移窗口内基本已过期，可整体丢弃，但要保证 EmailAddress.verified 完整 |
| taggit_tag / taggeditem | ② | 从未用过 |
| django_tasks_database_dbtaskresult | ② | 任务队列；**割接前排空**（邮件靠它发）|
| django_session | ② | 建议丢弃（全员重登）|
| django_admin_log | ② | 本项目后台非 Django admin |
| django_content_type | ②（**导入器要拿它当解码表**）| page.content_type_id → app_label|model 的映射全靠它 |
| django_cache | ② | 纯缓存（限流计数、心跳）|
| django_migrations | ② | |
| auth_group | **①** | 7 个业务组（交大用户/校外用户/内容编辑/赛事管理员/内战管理员/认证作者/投稿者）|
| auth_group_permissions / accounts_user_groups | ① | user→group 映射是业务数据 |
| accounts_user_user_permissions | ② | Django 权限位可再生 |

## 三、导入器 SELECT 规格

### 3.1 wagtailcore_page（28 列）

id（PK，**子表、评论、revision.object_id 都引用它，新表建议沿用原 id**）；path varchar(255) UNIQUE（treebeard 物化路径，每层 4 字符）；depth（根=1，首页=2，栏目/固定页=3，文章=4）；numchild；title / draft_title；slug（仅同级唯一）；url_path（全路径含首尾斜杠）；live 0/1；has_unpublished_changes；seo_title；show_in_menus；search_description；go_live_at/expire_at/expired（本站流程不用，多为 NULL/0）；content_type_id（→django_content_type，**决定该行属于哪个子表**）；owner_id NULL（author 为空时回填）；locked/locked_at/locked_by_id（未用）；latest_revision_created_at；first_published_at/last_published_at；**live_revision_id（当前已发布版本）**；**latest_revision_id（最新草稿）**；translation_key（单语言下与 id 一一对应，可弃）；locale_id（恒 1）；alias_of_id（未用）。

**树结构 → 新 pages 表的映射规则**：
1. 实际树：`id=1 root(depth1)` → `HomePage(slug=home, depth2)` → `news(ArticleIndexPage) + terms/privacy/about(StandardPage)` → 文章（depth4）。Site.root_page_id 指向 HomePage。
2. **对外 URL = url_path 去掉站点根前缀 `/home/`**：`/home/news/a/` → `/news/a/`。单站点下导入器直接计算最终 URL 落库。
3. 按 content_type_id 分流：`wagtailcore|page`(id=1) 丢弃；`content|homepage` → 首页配置（1 行）；`content|articleindexpage` → 栏目配置（intro）；`content|standardpage` → 新 pages 表；`content|articlepage` → JOIN content_articlepage（page id 相等）合成新 articles 表，**保留原 id** 使 comments_comment.page_id、置顶、moderation target 无需重映射。
4. path/depth/numchild 可不搬（新表存最终 URL 即可）；slug 仅同级唯一，新表若全局唯一需查冲突。

### 3.2 wagtailcore_revision（9 列）

id；created_at；approved_go_live_at NULL；user_id；**content TEXT(JSON)**；object_id（→page.id）；content_type_id（文章=44 之类，以 django_content_type 实际值为准）；base_content_type_id（页面 revision 恒为 wagtailcore|page）；object_str。索引 (content_type_id,object_id)、(base_content_type_id,object_id)。

**content JSON**：`page.serializable_data()` 完整快照——pk + 全部 Page 公共字段 + 子类字段 + wagtail_admin_comments；FK 存 id。
- **ArticlePage 草稿正文在 `body` 键**（v7.0 起是 Markdown 字符串；更早的历史 revision 里 body 是 StreamField JSON 数组——导入旧草稿需兼容）。其余键：summary、category、cover、author、tournament、comments_enabled、body_plain/body_words/body_minutes。空草稿判定 = title/summary/body 全空白。
- StandardPage 同为 body 键；首页/栏目是 intro。
- 已发布内容以 page 子表行为准（live_revision.content 应与之等值）。导入建议：文章表以 content_articlepage 为已发布值，latest_revision_id ≠ live_revision_id 时另存草稿。

### 3.3 wagtailimages_image（14 列）与 rendition（6 列）

**image**：id；title varchar(255)；**file varchar(100) = `original_images/<ascii 化文件名>`**（非 ASCII 替 `_`，总长 ≤94）；width/height；created_at；focal_point_x/y/width/height UNSIGNED NULL；uploaded_by_user_id NULL；file_size UNSIGNED NULL（懒填）；collection_id（恒根集合 1）；file_hash char(40)（sha1）；description varchar(255) ''（未用）；tags→taggit（未用）。

**rendition**：id；image_id FK CASCADE；filter_spec varchar(255)；focal_point_key char(16) ''；file varchar(100) = `images/<文件名>`；width/height。UNIQUE(image_id, filter_spec, focal_point_key)。

**rendition 文件命名规则**：`<原图主名(截断至 59-后缀长)>.[focal_point_key.]<spec 中 | 换成 .>.<ext>`；spec 的 `c50` 是 fill 的裁剪锚点参数，属于 spec 本身。本项目实际用过的 spec：`fill-88x88`、`fill-176x176`、`fill-288x288`、`fill-400x400`（头像）、`fill-960x540-c50`、`fill-1280x720-c50`、`fill-2400x1200-c50`（封面）、`fill-2400x640-c50`/`fill-2400x1350-c50`（横幅/首屏）、`fill-1600x700`（历史）、`fill-1200x630|format-jpeg`（OG 图）、`max-1600x1600`。WAGTAILIMAGES_FORMAT_CONVERSIONS：png/jpeg→webp q80（原图 png/jpeg 的缩略图是 .webp）。

### 3.4 wagtailembeds_embed（14 列）

id；url TEXT（b23.tv 短链）；max_width SMALLINT NULL；type char(10)；html TEXT（解析出的 iframe）；title/author_name/provider_name/thumbnail_url；width/height；last_updated；hash char(32) UNIQUE（url+max_width 缓存键，不透明即可）；cache_until NULL（仅「查不到」记录有 1 小时 TTL，查到的是 NULL=永久）。

### 3.5 allauth 两表

**account_emailaddress**：id；email varchar(254)；verified 0/1（登录/改邮箱前提）；primary 0/1（每用户至多一个主邮箱）；user_id FK CASCADE。UNIQUE(user_id,email)。

**account_emailconfirmation**：id；email_address_id FK CASCADE；created（默认 3 天过期；by-code 另有 15 分钟超时）；sent NULL；key char(64) UNIQUE。迁移可整体丢弃，保证 EmailAddress.verified 完整、未验证用户重走验证流程即可。

### 3.6 focal_point 现状（结论）

四个 focal_point_* 列存在但**本项目代码从不设置**；磁盘全部 rendition 文件名的焦点键一律是 `2e16d0ba` = sha1("None-None-None-None")[:8]，即所有图片焦点四列恒为 NULL。Go 新 schema 可安全删掉焦点字段（或保留可空默认），`2e16d0ba` 仅在复刻旧文件名时需要。

### 3.7 其他导入注意事项

1. 加密字段：三个 Fernet 列带 FIELD_ENCRYPTION_KEY 迁移，或割接时解密重加密（兼容历史明文）。
2. 口令哈希：`$argon2$...`（argon2-cffi）或 `pbkdf2_...`；Go x/crypto/argon2 可验证 PHC 串原样迁移。
3. 多态引用：core_broadcast.object_id、moderation_moderationitem.target_id、wagtailcore_revision.object_id 都是裸整数 + 类型判别列。
4. 大小写不敏感唯一（Lower() 表达式索引）：user.email、gameaccount.battletag、team.name（活跃）、membergroup.name——新 schema 用 COLLATE NOCASE 唯一索引等价。
5. 割接顺序：先排空任务队列表与 core_heldletter，再停机导出；django_session 丢弃则全员重登。
6. dev 库参考行数（非生产）：6 页、5 revisions、7 组、41 任务、67 缓存行、0 图片/0 embed（media/ 下 463 原图 + 317 缩略图 + fonts/ 分片）。
