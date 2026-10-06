# 217 复核 10：账号

范围：`accounts/`（模型、服务、注销与导出、表单、视图）、allauth 适配和表单、限流、`permissions.can_use`、组同步、停用/启用、会话、`LoggedInHintCookieMiddleware`、日历订阅（`core/calendar_feed.py`）。先读了 AGENTS.md、REVIEW-GUIDE、210 复核（A1–A13）、216 报告、设计 3、4 章和细节相关段落。

复现脚本：`findings/10-repro_accounts_test.py`（10-1、10-2、10-6 三条）。交回结论以后那一轮跑完了（测试机日志 `/srv/sjtu-ow-check/runs/20261007-034015-442b9ec.log`）：**10-1、10-6 已复现；10-2 没有复现**（验证那一步没有报错，已经改成「未复现」，不算缺陷）。跑法：
`bash scripts/remote-check.sh run uv run pytest -q -s -p no:cacheprovider handoff/rounds/217-second-review/findings/10-repro_accounts_test.py`（断言写的是现在有缺陷的行为，绿 = 复现了）。

## 中

### 10-1 后台对「投稿者」组关掉「投稿」→ 信号无限递归，之后验证过邮箱的成员一登录就 500

- **严重度**：中（要超管操作才会触发，但「先暂停投稿」最直观的做法正是这一步，触发以后全站成员都登录不了）
- **位置**：`accounts/signals.py:81-90`（`sync_submitter_when_groups_change`）、`accounts/services.py:197-210`（`sync_submitter_group`）、`accounts/signals.py:73-78`（每次 `User.save` 都同步）、`backoffice/views/members.py:262-279`（`role_restriction_add` 对任何组都能加限制，「投稿者」也在列表里，`backoffice/templates/backoffice/members/roles.html`）、`backoffice/forms.py:651-672`
- **问题**：`can_use(user, ARTICLE_SUBMIT)` 要看用户所在的组有没有限制。限制加在「投稿者」组自己身上时：人在组里 → `can_use` 为假 → `groups.remove` → `m2m_changed` 又调 `sync_submitter_group` → 人已经不在组里 → `can_use` 为真 → `groups.add` → 又触发信号 → 又为假……这一串都在同一个调用栈上，直到 `RecursionError`。
- **失败场景**：超管在后台「角色」页「投稿者」那一栏选「投稿」点「对这组关掉」→ 500。限制那一行是 `restriction.save()` 自动提交的，在 `post_save` 之前就写进去了，所以 500 以后**限制还在**。之后任何 `User.save()` 都会走 `sync_submitter_group`，登录时 `update_last_login` 就会存一次：每个验证过邮箱的成员（在组里的会被移出，不在组里的会被加进去）一登录就 `RecursionError` 500；改资料、验证邮箱、后台改这个人也一样。超管自己也在「投稿者」组里，退出后同样登录不了，只能在服务器上删这条限制。给自建组关掉投稿不会这样（只会从投稿者组移出，结果是稳定的）。
- **怎么验证**：`10-repro_accounts_test.py::test_restricting_article_submit_for_the_submitter_group_recurses`。用超管 POST `backoffice:role_restriction_add`（投稿者组，`feature=article_submit`）应该抛 `RecursionError`；不带信号写入这条限制以后，成员 POST `account_login` 也应该抛 `RecursionError`；对照组（自建组）正常。
- **状态**：已复现。测试机输出（原样）：
  ```
  成员验证过邮箱，在「投稿者」组里： True
  后台「角色」页对投稿者组关掉投稿： RecursionError maximum recursion depth exceeded
  之后任何验证过邮箱的成员登录： RecursionError
  ```
  脚本里的「对照」那一步没跑成：限制还在的时候 `member.groups.add(other)`（给这个人换组）本身也 `RecursionError` 了（`10-repro_accounts_test.py:97`），说明除了登录，**后台给任何人改角色也会 500**。「自建组关掉投稿不会递归」这个对照只读了代码，没跑出来。修法供参考：「投稿者」组不让加 `article_submit` 限制（表单拦），或者在算 `user_should_be_submitter` 时不把「投稿者」组本身算进去。

## 低

### 10-2（未复现，不算缺陷）改登录邮箱改成「没验证的账号」占着的地址

> 测试机上没有复现：加邮箱返回 `302 /accounts/confirm-email/`，输入验证码时**没有抛异常**（`输入发到新邮箱的验证码： NoneType None`）。可能 allauth 在这条路上另有处理，也可能脚本没有真走到 `set_as_primary`，没来得及查。下面是原来读代码的推断，留给后面的轮次判断。

- **位置**：`sjtu_ow/settings/base.py:251,257,258`（`ACCOUNT_CHANGE_EMAIL`、`PREVENT_ENUMERATION`、`UNIQUE_EMAIL`）；allauth 65.19.3 的 `account/forms.py:537-545`（开了防枚举，别人的地址也照样收下）、`account/models.py:70-80`（`can_set_verified` 只看**验证过的** `EmailAddress` 有没有冲突）、`internal/flows/email_verification.py:57-66` → `models.py:97-105`（`set_as_primary` → `user_email(..., commit=True)`）；`accounts/models.py:116-121`（`User.email` 不区分大小写唯一）
- **问题**：账号 X 注册时用了 a@，一直没验证（`User.email = a@`，`EmailAddress` 没验证）。持有 a@ 的人在已验证的账号 Y 上把邮箱改成 a@：加邮箱这一步不拦（防枚举），验证码发到 a@，验证时 `can_set_verified` 看不到冲突（X 的地址没验证），`set_as_primary` 先把 Y 的旧主邮箱改成非主、新地址存成已验证的主邮箱，然后 `user.save(update_fields=["email"])` 撞上 X 的 `User.email` → `IntegrityError`。请求不在事务里，前面两步已经落库：Y 的「主邮箱」是 a@ 而 `Y.email` 还是旧地址；X 以后也验证不了 a@（已经被 Y 验证）。
- **失败场景**：注册时没收到验证码、换个邮箱又注册了一个号的人，后来想把邮箱改回原来那个；或者有人先用别人的地址注册一个不验证的号占着。
- **怎么验证**：`10-repro_accounts_test.py::test_changing_email_to_an_address_an_unverified_account_holds`：登录 Y → POST `account_email`（`action_add`）→ 从会话里取 `account_email_verification_code` 的验证码 → POST `account_email_verification_sent`，应该抛 `IntegrityError`。
- **状态**：未复现（见上）

### 10-3 「改密码」页每人每分钟能试 5 次旧密码，216 给注销页加的「每小时 5 次」挡不住拿到会话的人试密码

- **位置**：`sjtu_ow/settings/base.py:261-271`（`"change_password": "5/m/user"`）；allauth `account/forms.py:594-598`（`clean_oldpassword` 直接 `check_password`，不走 `login_failed` 的按邮箱限流）；对比 `accounts/views.py:396-411`（`DELETE_TRIES_PER_HOUR = 5`）
- **问题**：设计 3.8（v7.19，210 的 A6）给注销页加限流，理由是「拿到会话的人可以在这里试密码」。但同样拿着会话，`/accounts/password/change/` 每分钟能试 5 次（每天 7200 次），猜中以后直接改掉密码、把本人踢下线。重新验证页（`reauthenticate`）走 `adapter.authenticate`，有 `login_failed` 的 `5/300s/key`，比它严。
- **失败场景**：会话被偷（公共电脑没退出），对方在改密码页慢慢试弱密码。
- **怎么验证**：带会话连续 POST 6 次错误的 `oldpassword`，前 5 次是 200（表单报错），第 6 次才被限流；同一分钟过去后又能试 5 次。
- **状态**：已核对代码（配置和 allauth 源码），没复现

### 10-4 `ON_DELETION` 写着退役记录「保留」，代码是删掉

- **位置**：`accounts/services.py:356`（`"teams.TeamAlumnus.user": "保留，退役记录显示「已注销用户」"`）对比 `teams/services.py:448-451`（`leave_all_teams` 把这个人的 `TeamAlumnus` 全部删除）
- **问题**：设计 3.8 说注销时每个指向用户的字段怎么处理以 `ON_DELETION` 为准、有测试数一遍；但测试只数键、不核对写的处理方式。代码按设计细节 5.4（L287「注销账号时连同记录一起删」）删掉了，清单写反了。只是清单错，行为和细节文档一致。
- **怎么验证**：`grep -n TeamAlumnus accounts/services.py teams/services.py`；或者给一个有退役记录的人注销，看 `TeamAlumnus.objects.filter(user=...)` 是空的。
- **状态**：已核对代码

### 10-5 别人用你的邮箱抢注一个不验证的号，你找回密码接手后，账号里「同意协议」「同意跨境存储」的时间是对方勾的

- **位置**：`accounts/adapter.py:92-107`（同意时间在注册时写入）；allauth `internal/flows/password_reset_by_code.py:49-55`（用验证码找回密码会顺带把邮箱标成已验证）；`sjtu_ow/settings/base.py:257`（开了防枚举，本人再注册只会收到「账号已存在」的信，叫他去找回密码）
- **问题**：注册不需要证明你拥有这个邮箱。A 用 v@ 注册（昵称、是否交大也是 A 填的），不验证。v@ 的主人注册时被告知「已存在」，只能用找回密码接手这个号：邮箱随即算已验证、登录。主人从没勾过设计 3.1 要求分开单独勾选的两项同意（15.3 的跨境存储同意），库里的 `agreed_terms_at`、`agreed_cross_border_at` 是 A 点的；昵称、是否交大也是 A 填的。
- **失败场景**：恶意抢注，或者有人填错了邮箱、刚好是别人的地址。
- **怎么验证**：用 v@ 走一次注册不验证；再对 v@ 走「找回密码 → 验证码 → 设新密码 → 登录」，看 `EmailAddress.verified` 已为真、同意时间还是第一次注册的时间，中间没有页面让本人勾选同意。
- **状态**：已核对代码（allauth 源码），没复现

### 10-6 游戏 ID「全站不区分大小写唯一」只管 ASCII；数字校验认全角和上标数字

- **位置**：`accounts/models.py:204-214`（`digits.isdigit()`）、`:233-239`（`Lower("battletag")` 唯一约束）、`:258-262` 和 `accounts/forms.py:183-191`（`battletag__iexact`）；`accounts/models.py:306-321`（QQ、手机号用 `isdigit()`）
- **问题**：SQLite 的 `LOWER()` 和 `LIKE`（Django 的 `iexact`）只对 ASCII 字母不分大小写，所以 `Émile#1234` 和 `émile#1234` 能分别绑在两个账号上（设计 3.5.2：全站不区分大小写唯一）。Python 的 `str.isdigit()` 认全角 `１２３４` 和上标 `¹²³⁴⁵`，所以 `Émile#１２３４` 也能绑上，看起来和 `Émile#1234` 一样；QQ「１２３４５６」、手机号「1３８００１３８０００」也能通过「5 到 11 位数字」「11 位中国大陆手机号」的校验，管理员照抄就是错的号码。
- **失败场景**：冒用别人带重音字母的 BattleTag（设计说管理员可以删被冒用的游戏 ID，但它本来应该在绑定时就被拦下）；联系方式里存着全角数字。
- **怎么验证**：`10-repro_accounts_test.py::test_battletag_uniqueness_is_ascii_only_and_digits_are_unicode`（三个账号各自绑上 `Émile#1234`、`émile#1234`、`Émile#１２３４`；三个联系方式都能通过校验）。
- **状态**：已复现。测试机输出（原样）：
  ```
  三个账号各自绑上了： ['Émile#1234', 'Émile#１２３４', 'émile#1234']
  联系方式 qq '１２３４５６'：通过
  联系方式 phone '1３８００１３８０００'：通过
  联系方式 qq '¹²³⁴⁵'：通过
  ```

### 10-7 导出里的赛事名单快照只有昵称和游戏 ID，没有快照里的段位和「是否交大」

- **位置**：`accounts/services.py:563-574` 对比 `tournaments/models.py:324-331`（`RegistrationMember` 快照里还存着 `is_sjtu`、`rank_tank/damage/support`、`is_captain`）
- **问题**：设计 3.8 说导出包括「赛事报名（自己在名单里的，含名单快照）」。快照里关于本人的段位和是否交大，站点存着，导出里没有。
- **怎么验证**：报一次整队赛事，导出 JSON 里 `tournament_registrations` 只有 `nickname_snapshot`、`battletag_snapshot`。
- **状态**：已核对代码

### 10-8 整张保存 `User` 的表单会把同一时间别的请求改的列写回旧值（包括 `is_active`）

- **位置**：`accounts/views.py:108-118`（个人中心 `ProfileForm(instance=request.user)` 有效时 `form.save()`，没有 `update_fields`）；`backoffice/views/members.py:128-143`（后台 `UserForm` 同样整张保存）；`core/autosave.py:113-116`
- **问题**：ModelForm 的 `save()` 把请求开头读出来的整行写回去。没有包住整次请求的事务，所以几毫秒内另一个请求做的改动会被覆盖：管理员停用的同时，这个人的自动保存（打字时每隔几秒一次）把 `is_active=True`、`deactivation_note=""` 写回去，等于又启用了；后台管理员编辑某人的同时这个人注销了，后台的保存会把真实邮箱、密码哈希、`is_active=True` 写回这个刚匿名化的账号（邮箱验证记录已删，要重新验证才能登录）；`calendar_version`、头像、活动通知开关同理。
- **状态**：推测（读代码推出来的竞态，窗口是一次请求的时长，没构造）

## 查过没问题

- **日历订阅的版本号（216）**：签名的载荷是 `pk` 或 `[pk, version]`，只有服务器能签；`[pk, true]` 虽然能过 `isinstance(…, int)`（`True` 当 1 查），但要伪造签名，不可利用。换地址后：195 以前带时间戳的老地址、195 以后不带版本的地址都按版本 0 解，和 `calendar_version>=1` 对不上，都失效；`Signer` 和 `TimestampSigner` 用同一个 salt，互相解时要么签名不对、要么 base64/JSON 解出 `ValueError` 被接住；三个元素的列表、非整数一律 None。查询带 `is_active=True`，停用和注销的地址立刻失效；换地址是 POST 加 CSRF；`Cache-Control: private`、`noindex`；按 IP 限流。
- 注销（3.8）：顺序（先撤报名再删游戏 ID、先退临时队伍）、`is_superuser`/`is_staff` 清掉（A9）、邮箱换成 `.invalid` 并删验证记录、密码作废、组清空的时机（在 `save` 之后）、本人上传的头像图片和记录删掉、昵称/宣言的审核快照（包括 `save` 刚送进去的那条，`submit` 是同步写的）删掉、等待中的入队申请取消、队长先拦、限流 5 次/小时、其他设备的会话因为 `is_active=False` 和密码哈希变化都失效、注销的账号不能再启用（后台 `reactivate_account` 拦）。做完事顺带的信：注销时 `HeldLetter(actor=user)` 删掉，`settle` 在没人可问时照设计 10.5 直接发。
- 导出：`EXPORTED`/`NOT_EXPORTED` 和项目里所有指向用户的外键一致；只有本人的数据；游戏 ID 删掉以后的内战报名不再 500（`battletag` 属性兜底）；限流 5 次/小时、`no-store`。
- `can_use`：未登录、停用为假；单人规则优先，其次组限制，默认开放，和 4.3.2 一致。
- 投稿者组同步：验证邮箱（`email_confirmed` 和 `EmailAddress` 的 `post_save`）、停用/启用、组变化、单人规则和组限制的增删都会重算（10-1 那一种情况除外）。
- 停用/启用走 service（A8）：取消待审批申请、暂停招募、刷新公开页、移出/放回投稿者组、启用时清空原因。
- 自动保存：联系方式的类型撞车在表单里报（A1），`autosave_together` 把类型和内容绑在一起（A3）；改段位的部分保存会更新 `ranks_updated_at`（A7）；游戏 ID、联系方式按 `user=request.user` 取（A13 有测试）。
- 改邮箱要重新输密码（A5，`ACCOUNT_REAUTHENTICATION_REQUIRED`），后台的「帐号」页不能改邮箱；新后台的 `UserForm` 只有昵称和是否交大。
- 邮箱只给超管看（A2 决定以后）：成员分组搜人、文章作者下拉按 `sees_emails`；其余后台模板里出现邮箱的（用户列表和编辑、指定队长）都是超管专用；日志里的人名走 `User.__str__`（昵称）。
- 登录提示 Cookie：登录时设置、退出或会话失效后下一次请求删除；不含身份信息。
- allauth 限流按 Caddy 给的真实 IP（`get_client_ip`）；注册、找回密码在开了防枚举时提示一样；`render_mail` 按收信地址查昵称，只发给这个地址本人。
- `createsuperuser`、`verify_email` 只在服务器上用，`trust_email` 把其他地址设为非主。

## 没来得及看

- 10-2 为什么没复现（验证码那步没有报错，没查 allauth 在哪里拦住或绕开了）
- 注册和验证码发信的速度（`confirm_email` 1/10s/key，注册 20/m/ip）能不能把站点的 SMTP 日配额刷完；只读了配置
- `accounts/images.py` 头像解码（02 那块在看）
- 个人中心模板逐页的 XSS、HTMX 片段（12 那块）
- `/wagtail/` 下超管专用的用户表单能不能重新启用注销过的账号、直接改邮箱（04 那块；REVIEW-GUIDE 说那里绕过新后台的规则是有意的）
- `core/agenda.py` 的 `items_for` 给日历的内容（草稿、取消的内战会不会进去，13 那块）
