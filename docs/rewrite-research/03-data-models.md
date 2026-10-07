# 03 · 数据模型盘点（37 个自有模型）

来源：第一轮模型盘点代理。基线 `ec44ae4`。逐字段明细和第三方表处置见 `04-data-dictionary.md`。

## ① 各应用模型表

### accounts（6 个模型，10 个迁移）
| 模型 | 用途 | 关键字段 | 关系/约束 |
|---|---|---|---|
| `User` | 站内用户，邮箱登录（username 弃用）| email(unique,254)、nickname(16字)、is_sjtu、sjtu_verified_via/at、agreed_terms_at、agreed_cross_border_at、deactivation_note(200)、motto(30)、main_role/flex_roles(choices/CSV)、show_rank、accepts_announcements、calendar_version、avatar FK | 继承 AbstractUser；`Lower(email)` CI 唯一约束（accounts/models.py:52-121）|
| `AvatarSubmission` | 头像上传记录（上传即生效，编辑可撤下）| status(pending/approved/rejected/withdrawn/taken_down)、reason(moderation.Category)、note、reviewed_by/at | FK user CASCADE、image SET_NULL；条件唯一：每用户仅一条 pending |
| `GameAccount` | 游戏 ID（Battle.net tag + 三位置段位分数）| battletag(64)、rank_tank/rank_damage/rank_support SmallInt、ranks_updated_at（save 时自动盖时间戳）| FK user CASCADE；`Lower(battletag)` CI 全局唯一；格式校验「名称#4-6位数字」|
| `ContactMethod` | 联系方式（类型+内容）| type(qq/wechat/phone/other)、value(64)，按类型单独校验 | FK user CASCADE；(user,type) 唯一 |
| `FeatureGroupRestriction` | 按用户组禁用功能 | feature(7 选 1：team_create/team_apply/tournament_register/scrim_signup/article_submit/article_comment/avatar_upload)、note、updated_by | FK Group CASCADE；(group,feature) 唯一 |
| `FeatureUserRule` | 按用户覆盖功能（allowed 单独允许）| feature、allowed、note、updated_by | FK user CASCADE；(user,feature) 唯一 |

**邮箱验证不在 accounts**：django-allauth 的 `account_emailaddress`（verified/primary）+ `account_emailconfirmation`；`trust_email` 可服务端直接标已验证（accounts/services.py:158-183）。功能权限判定：组禁 + 用户规则（accounts/services.py:19-35，7 个预置组）。

**账号注销 = 原地匿名化，永不删除行**（accounts/services.py:368-421）：email→`deleted-{pk}@deleted.invalid`、昵称→「已注销用户」、is_active/staff/superuser=False、清头像/宣言/角色/交大认证、`set_unusable_password()`；删除 GameAccount、ContactMethod、EmailAddress、FeatureUserRule、HeldLetter(actor)、MemberGroupMembership、未决 TeamApplication（撤回）、ScrimSignup、IndividualSignup、头像图片；**保留**：文章 author、评论 author/reply_to_user、CommentLike、TeamAlumnus、RegistrationMember（名单快照）、各 `*_by` 操作人列。逐列处置表 ON_DELETION 在 accounts/services.py:328-365，导出清单在 :427-473。停用只置 is_active+deactivation_note，并撤回 pending 申请、暂停其任队长的战队招募（:799-844）。

### content（6 个模型，12 个迁移）
| 模型 | 用途 | 关键字段 | 关系/约束 |
|---|---|---|---|
| `ArticleCategory` | 文章分类（snippet）| name(32,可空=autosave 半成品)、slug(64)、sort_order、allow_submission | 条件唯一：slug≠"" 时唯一 |
| `HomePage` | 全站唯一首页（max_count=1）| — | InlinePanel pinned_articles；子页 slug 保留字表 RESERVED_CHILD_SLUGS |
| `HomePagePinnedArticle` | 首页置顶（Orderable）| — | (page,article) 唯一；≤3 篇 |
| `ArticleIndexPage` | 文章栏目页 | intro(Text) | parent=HomePage |
| `ArticlePage` | 文章 | category FK(PROTECT)、cover FK(SET_NULL)、summary(200)、body(Text, Markdown)、body_plain/body_words/body_minutes（save 时派生）、author FK(PROTECT)、comments_enabled、tournament FK(SET_NULL) | author 缺省取 owner；was_updated=发布 1 天后又改；权限只允许作者本人发布/下线 |
| `StandardPage` | 普通页（协议等，Markdown）| body(Text) | parent=HomePage |

**草稿与修订**：完全依赖 Wagtail 内建 `wagtailcore_revision`（PageRevision JSON 快照）+ `wagtailcore_pagelogentry`；后台表单的 go_live_at/expire_at 写入 revision 的 `approved_go_live_at` 实现定时上下线（backoffice/forms.py:103-152）。自动保存不落独立表，复用同一视图做部分保存 + 日志合并（core/autosave.py）。

**图片**：Wagtail 默认 `wagtailimages.Image`（含 focal point、collection、rendition）；头像统一进「用户头像」collection；缩略图缓存 LocMem、PNG/JPEG 一律转 WebP（settings/base.py:324-329）。

**B 站嵌入**：`wagtailembeds_embed` + 自定义 `content.embeds.BilibiliEmbedFinder`：命中永久缓存（cache_until=None），失败 1 小时后重试（content/embeds.py:24-28,73-130）。

### core（8 个模型，24 个迁移）
| 模型 | 用途 | 关键字段 |
|---|---|---|
| `HealthProbe` | /healthz 写探针（事务内回滚）| token(32) |
| `SiteSettings` | 全站设置单例（一行）| SMTP（host/port/security/username/smtp_password 加密/from_*）、站点信息（description/share 图/hero/founded_on/qq_group_url）、5 张栏目横幅 FK、社区参数（team_max_members=10、team_max_captained=3、max_game_accounts=5、scrim/tournament_reminder_hours）、备份 R2（backup_s3_*，secret_access_key 加密）、AI 审核（enabled/model/daily_limit=2000/image_enabled/alert_email/api_key 加密/base_url/extra_body JSON/timeout/max_output_tokens）、排版（font_css_path/generated_at）|
| `FontFamily` / `FontFace` / `TypographyRule` | 字体库三件套 | 见 06 基础设施 |
| `PrerenderedPage` | 静态化页面登记 | path(unique,500)、kind(12 种)、status(pending/ready/failed)、requested_at/generated_at、content_hash、bytes、error |
| `Broadcast` | 群发通知记录 | kind、object_id(Generic PositiveInt)、audience(everyone/participants)、before(第几封)、note、moved_from、subject、sent_by、recipient_count、waits_for_publish |
| `HeldLetter` | 待发信（204 起）| batch(UUID db_index)、actor FK CASCADE、letter JSON（全文）、recipients JSON [[addr,name]…]、back、in_back_office、state(waiting/sent/skipped)、decided_at |

core 附属：操作记录 = Wagtail log（19 种自定义 action，core/admin_log.py:18-38）；任务队列 = django_tasks_database_dbtaskresult；退订无独立表（签名 token 翻转 accepts_announcements）；限流计数存 `django_cache` 表；**已删模型**：core/0011 删 lfg 残留。

### teams（4 个模型，5 个迁移）
| 模型 | 用途 | 关键字段 | 关系/约束 |
|---|---|---|---|
| `Team` | 战队（解散=软删除）| name(16)、description(500)、logo FK(SET_NULL)、is_recruiting、recruiting_roles(CSV)、member_contact(100，仅队内可见)、disbanded_at、created/updated_at | 条件唯一：未解散队名 CI 唯一 |
| `TeamMembership` | 队内成员 | role(captain/member)、joined_at | (team,user) 唯一 + 每队至多一队长（条件唯一）|
| `TeamApplication` | 入队申请 | role_tank/damage/support(Bool)、message(200)、status、decided_by/at、decision_note、captain_reminded_at(一周提醒一次) | 每队每人一条 pending（条件唯一）|
| `TeamAlumnus` | 退役成员记录 | role(离队时身份)、joined_at/left_at、reason(left/removed) | (team,user) 唯一 |

### members（2 个模型，3 个迁移）
| 模型 | 用途 | 关键字段 | 约束 |
|---|---|---|---|
| `MemberGroup` | 展示页分组 | name(20,空=建设中不展示)、description(200)、is_visible、sort_order | 非空名 CI 唯一 |
| `MemberGroupMembership` | 分组成员 | user、title(职务，每段≤10字) | (group,user) 唯一；只能选已加入用户 |

### tournaments（5 个模型，15 个迁移）
| 模型 | 用途 | 关键字段 | 约束 |
|---|---|---|---|
| `Tournament` | 赛事 | title(100)、summary(300)、description(Markdown)+description_plain、cover、starts_at、registration_opens_at/closes_at（草稿可空，发布必填）、roster_min/max(默认 5/6)、sjtu_only、registration_mode(individual/team，有人报名后不可改)、auto_approve(仅整队有效)、status、published_at、reminder_sent_at、moved_from(改时间后待通知)、participant_contact(仅参赛者可见) | Check：1≤min≤max≤20、opens<closes |
| `Registration` | 报名（一队一赛事一条）| team FK(nullable=临时队, PROTECT)、status、team_name(16,快照)、roster_version、submitted_by/at、status_note(300) | (tournament,team) 唯一 + team_name 非空 Check；索引 (tournament,status)、(updated_at,id) |
| `RegistrationMember` | 名单冻结快照 | nickname/battletag/is_sjtu/rank_* 快照、is_captain、is_active(占名额)、game_account FK(SET_NULL) | 每赛事每用户仅一条 active |
| `RegistrationStatusLog` | 报名状态日志（append-only）| action(9 种)、from_status/to_status、actor_type(captain/admin/system/member)、actor_user、roster_version、roster_snapshot(JSON) | |
| `IndividualSignup` | 个人报名/散人池 | game_account FK(SET_NULL，未结束赛事会拦删)、role_* 三 Bool、registration FK(SET_NULL，编入临时队后指向) | (tournament,user) 唯一 + 至少一个位置 Check |

### scrims（2 个模型，5 个迁移）
| 模型 | 用途 | 关键字段 | 约束 |
|---|---|---|---|
| `Scrim` | 内战 | title(100)、description+description_plain、starts_at(草稿可空)、signup_closes_at(空=开始前都可报)、format(rq_5v5/rq_6v6/open_5v5/open_6v6)、sjtu_only、status、teams_generated_at、roster_changed_at(分队过期标记)、reminder_sent_at、moved_from | 索引 (status,starts_at) |
| `ScrimSignup` | 报名 + 分队结果就存在这 | game_account FK(SET_NULL)、role_* 三 Bool、is_selected(上场)、team("a"/"b")、assigned_role、rating_used(分队时用的分数) | (scrim,user) 唯一 + 至少一位置 Check |

分队规格常量 ROLE_REQUIREMENTS/TEAM_SIZES（scrims/models.py:44-54）：5v5=1坦/2输/2援，6v6=2/2/2。

### moderation（2 个模型，6 个迁移）
| 模型 | 用途 | 关键字段 | 约束 |
|---|---|---|---|
| `ModerationItem` | AI 送审记录（AI 只写此表）| target_type(11 种)+target_id+field、excerpt、full_text(长文待巡查)、text_hash、risk(none/low/medium/high/unknown=无法判定)、categories JSON、reason/quote、model、in/out_tokens、status(pending/ok/handled/ignored)、reviewed_by/at、handling_note、checked_at、notified_at、attempts/last_error/failed_at（=「没看成」，与 unknown 分开）| (target_type,target_id,field,text_hash) 唯一；索引 (status,risk,created_at) |
| `ModerationUsage` | 每日用量记账 | date(unique)、calls、items、input/output_tokens | |

### comments（2 个模型，2 个迁移）
| 模型 | 用途 | 关键字段 | 约束 |
|---|---|---|---|
| `Comment` | 评论（两层树）| page FK(ArticlePage)、author FK(PROTECT)、parent FK(self,只指向顶层)、reply_to_user(SET_NULL)、body(≤500)、created/edited_at、is_pinned、is_hidden、is_deleted、like_count(冗余) | 每页至多一条置顶（条件唯一）；索引 (page,created_at)、(page,is_pinned,like_count) |
| `CommentLike` | 点赞 | created_at | (comment,user) 唯一 |

### integrations（0 个模型，3 个迁移）
墓碑：0001 建 ApiClient/ApiRequestLog，0002 建 WebhookDelivery，0003 全删；tournaments/0004 依赖 integrations/0001，必须留在 INSTALLED_APPS。

无模型的应用：backoffice、search（backoffice 纯界面，search 用 wagtailsearch 表）。

## ② 加密字段清单（Fernet，密钥 FIELD_ENCRYPTION_KEY 环境变量）

| 位置 | 字段 |
|---|---|
| core.SiteSettings | smtp_password（core/models.py:62）|
| core.SiteSettings | backup_s3_secret_access_key（:209）|
| core.SiteSettings | moderation_api_key（:249）|

实现 core/fields.py:15-50：读时透明解密，旧明文原样返回直到下次保存；仅这 3 处。备份密钥 BACKUP_ENCRYPTION_KEY 刻意不放库（base.py:344-348）。

## ③ 状态机清单

| 状态机 | 状态集合 | 迁移规则（服务层强制）|
|---|---|---|
| Tournament.status | draft→published→finished / cancelled | cancelled 终态不可再动；draft 缺字段拒发；finish 仅 published；cancel 双向可（draft 需齐字段）；draft 且无报名才可删 |
| Registration.status | pending→approved / rejected；approved→withdrawn（revoke）| approve 仅 pending；占名额 = pending+approved；每次变化写 RegistrationStatusLog |
| IndividualSignup | 散人池（registration=None）→ 已编队（指向临时队）| is_placed |
| Scrim.status | draft→published→finished / cancelled | 与 Tournament 同构；开始 6 小时自动结束；仅 draft 可删 |
| ScrimSignup 分队 | 未选→上场 A/B 队（team+assigned_role+rating_used 落行上）| 有人退出后 roster_changed_at 标记分队过期 |
| TeamApplication.status | pending→approved / rejected / cancelled | 队满或解散转 cancelled；停用自动撤回 |
| Team 生命周期 | 现役→解散（软删 disbanded_at）| 行保留供报名引用 |
| AvatarSubmission.status | pending→approved/rejected/withdrawn/taken_down | v6.73 起上传即 approved；撤下走 take_down_avatar |
| ModerationItem.status | pending→ok / handled / ignored | ok=AI 判无风险；handled=请作者修改等处置 |
| HeldLetter.state | waiting→sent / skipped | 「发信」页人工决定 |
| FontFace.status | pending→processing→ready / failed | 字体切片任务推进 |
| PrerenderedPage.status | pending→ready / failed | |
| User 生命周期 | 活跃→停用→注销（匿名化，@deleted.invalid 终态不可恢复）| 注销即摘超管 |

## ④ 数字汇总

- **模型总数 37**（accounts 6、content 6、core 8、teams 4、members 2、tournaments 5、scrims 2、moderation 2、comments 2、integrations 0）
- **迁移 85 份**（accounts 10、content 12、core 24、teams 5、members 3、tournaments 15、scrims 5、moderation 6、comments 2、integrations 3）
- 第三方表：Wagtail 全家、allauth、taggit、django（session/admin_log/content_type/cache）、django_tasks_database_dbtaskresult——逐张处置见 04
- **注意**：仓库里的 `data/db.sqlite3` 是过期演示快照（停在旧迁移），**以迁移文件为准**

## ⑤ 对 Go 重构与数据迁移有影响的细节

1. SQLite：WAL + `transaction_mode=IMMEDIATE` + `timeout=5` + `PRAGMA synchronous=NORMAL`（base.py:107-122）；限流、健康探针依赖 IMMEDIATE 串行写。
2. ID 惯例：项目应用 PK 一律 BigAutoField；allauth 表 32 位；URL 转换器 `<id:pk>` 上限 18 位、`core.converters.as_id()`。
3. 时区：USE_TZ=True、TIME_ZONE=Asia/Shanghai，DateTimeField 存 UTC；段位分数是自定义编码 int（0-39，前 500=40，accounts/ranks.py:17-38）。
4. 软删/硬删混合：Team 软删、Comment 双软标志、User 注销匿名化；迁移须保序（如删账号前先撤内战报名）。
5. 加密字段：3 个 Fernet 列需 FIELD_ENCRYPTION_KEY 解密再入新库；迁移工具兼容「明文/密文」两种存量。
6. 派生字段（body_plain/words/minutes、description_plain）在 save() 钩子维护，Go 写路径必须复刻。
7. JSON 列：roster_snapshot、categories、moderation_extra_body、slices、letter/recipients——SQLite 里就是 TEXT。
8. 跨对象引用：Broadcast 与 ModerationItem 用 (kind/target_type, object_id) 手写多态，迁移按 target_type 分别解析。
9. 缓存即数据：限流计数、worker 心跳在 django_cache 表；该表丢弃安全（可再生）。
10. 两处刻意的用户可见文案依赖库缺失：删掉的游戏 ID 显示「（游戏 ID 已删除）」（SET_NULL）、注销用户显示「已注销用户」（匿名化）；PROTECT 用于 comments.author、RegistrationMember.user、Registration.team、ArticlePage.category/author——Go schema 照搬这两种 on_delete 语义。
