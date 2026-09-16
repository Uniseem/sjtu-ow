# 005 实现报告

## 结论

T1–T6 已完成：SMTP 密码下沉到 `EncryptedTextField`（任意 ORM 写入都是密文，明文历史下次保存时加密），`GameAccount` / `ContactMethod` / 功能权限两张表，`/me/` 四个页面（HTMX 卡片），`can_use` 按 4.3.2 判定，`init_site` 建齐全部预置组并幂等分配本轮权限。

## 逐条结果

### T1 SMTP 加密字段

- 新增 `core.fields.EncryptedTextField`：读取时 Fernet 解密；无法解密且不像密文的当作明文历史返回；下次 `save()` 重新加密。看起来像 Fernet（`gAAAAA`）但当前密钥解不开时，报错说明是密文/密钥不匹配，而不是含糊的「密钥错误」。
- `SiteSettings.smtp_password` 改为该字段。`SiteSettingsAdminForm` 仍不回显、留空保留原密码，表单只赋明文，由字段加密（避免双重加密）。
- `build_smtp_backend` 直接使用已解密的 `site.smtp_password`。
- 注意：不能走 `TextField.get_prep_value()`，它会先 `to_python()` 把密文解掉，导致每次写入都换新 token。

### T2 游戏 ID 与段位

- `GameAccount`：`battletag` 表达式唯一约束 `Lower()`，三个位置 `smallint` 可空，`ranks_updated_at` 仅在段位变化时更新。
- `accounts.ranks`：附录 A 编码/解码/中文显示；前 500 = 40，未定级 = `None`。
- BattleTag 校验按 3.5.2；占用文案「该游戏 ID 已被其他账号绑定，如有疑问请联系管理员」。
- 上限读 `SiteSettings.max_game_accounts`（默认 5）。
- `deletion_blocked_reason()` 留空实现，注释标明 M6（未结束内战报名）和 M3（车帖一并删除）。

### T3 联系方式

- `ContactMethod`：`qq` / `wechat` / `phone` / `other`，`(user, type)` 唯一，各类型校验按 3.5.3。
- 默认 Django 权限 `accounts.view_contactmethod`；前台 `/me/contacts/` 只读自己的，别人的 pk 返回 404。

### T4 个人中心

- `/me/`、`/me/game-accounts/`、`/me/contacts/`、`/me/security/`。战队和报名页面未做；导航里这两项可见但不可点。
- 基本资料：昵称、是否交大（改完 `post_save` 换组）。
- 游戏 ID：卡片 + 段位徽章 +「段位更新于 X 前」；新增/编辑/删除走 HTMX 片段（`{% partialdef %}`），无 JS 时整页表单仍可用。
- 联系方式：行内增删改。
- 账号安全：链到 allauth 修改密码 / 修改邮箱。
- 资料不完整时所有个人中心页顶部提示条；HTMX 成功后用 `hx-swap-oob` 更新提示条。
- 桌面左侧 `menu`，手机顶部 `tabs`（可横向滚动），无内联 `style`。

### T5 功能权限

- `FeatureGroupRestriction`、`FeatureUserRule`。
- `accounts.permissions.can_use`：单用户规则 > 任一所在组限制 > 默认 True。未登录/停用为 False。
- `feature_denied_message()` 返回「你暂时无法使用此功能，如有疑问请联系管理员」。
- Wagtail `ModelViewSet` 放在设置菜单「功能权限」，`SuperuserOnlyPolicy`；用户列表「更多」和用户编辑页有快捷入口。`updated_by` 在保存时写入当前管理员。本轮没有可挂接的业务按钮，判定由测试覆盖。

### T6 `init_site`

- `get_or_create` 七个组：交大用户、校外用户、内容编辑、赛事管理员、内战管理员、认证作者、投稿者。
- 五个后台角色加 `wagtailadmin.access_admin`；赛事/内战管理员加 `accounts.view_contactmethod`。`permissions.add` 幂等，不改成员关系。
- 命令里写明其余权限和页面树等到后续里程碑。

## 验收输出

### 1. ruff / pytest / makemigrations / check --deploy

```
All checks passed!
115 files already formatted
```

```
97 passed in 6.59s
```

```
No changes detected
```

```
DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod \
DJANGO_SECRET_KEY=ci-not-for-production-use-a-long-random-string-at-least-fifty-chars \
FIELD_ENCRYPTION_KEY=ci-not-for-production \
DJANGO_ALLOWED_HOSTS=example.com \
DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com \
SITE_URL=https://example.com \
DJANGO_SECURE_SSL_REDIRECT=true \
uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

### 2. ORM 写 SMTP 密码后查原始库

```
>>> site.smtp_password = "verify-005-orm-plain"; site.save()
>>> raw: (1, 120, 'gAAAAABqqjyTToQUhSKL8e9HqIf8l-Jr')
>>> orm plaintext roundtrip: verify-005-orm-plain
>>> decrypt raw: verify-005-orm-plain
```

Fernet 前缀 `gAAAAA`，长度 120，不是明文。写完已把原值（空）写回去。

### 3. 浏览器 `/me/` 375px

视口 `innerWidth=375`，`[style]` 数量 0。登录后资料已完整，顶部提示条为空。截图：

- `artifacts/me-profile-375.png`
- `artifacts/me-game-accounts-375.png`
- `artifacts/me-contacts-375.png`

手机端为顶部标签（可横向滚动）；游戏 ID 卡片显示钻石 3 / 黄金 1 / 前 500；联系方式显示 QQ。点「编辑」后 HTMX 换成段位下拉表单。

### 4. 补全资料后提示条消失

注册 `live005b-1789541589@example.com`（验证码 `064665`）→ 登录 →：

| 步骤 | 结果 |
|---|---|
| GET `/me/` | 提示条在（缺游戏 ID 和联系方式） |
| POST 游戏 ID `LiveFive#1234` 坦克 22 / 输出 14 / 支援 40 | 200，卡片出现「钻石 3」 |
| GET `/me/contacts/` | 提示条仍在 |
| POST QQ `123456789` | 200 |
| GET `/me/` 与 `/me/contacts/` | 「资料尚未完整」消失 |

### 5. `can_use`

```
default True
group deny False
user allow True
```

给「校外用户」加 `tournament_register` 限制后 `False`；再给该用户 `FeatureUserRule.allowed=True` 后 `True`。验收数据已从本地库删掉，避免误伤其他校外用户。

### 6. `init_site` 连续两次

两次输出相同：七个组「已确保用户组存在」，并写「不会改写已有用户组成员关系」。随后查询 `count= 7`，无重复行。

### 7. 注册登录回归与 `/healthz`

- 注册 → 验证码 321236 / 064665 → 登录 `ow_logged_in=1` → `/me/` 200。
- worker 在跑：`/healthz` **200**，`worker_heartbeat` ok。
- 第二个连接 `BEGIN IMMEDIATE` 期间：

```
status= 200
elapsed_s= 0.233
{"status": "ok", "checks": {"database": {"ok": true, "detail": "busy: another write in progress"}, ...}}
```

### 8. docker / caddy

```
Successfully built 24a93ae041c2
Successfully tagged sjtu-ow:ci
```

```
docker run --rm -e CADDY_SITE_ADDRESS=http://localhost \
  -v $PWD/deploy/Caddyfile:/etc/caddy/Caddyfile:ro \
  caddy:2.10-alpine caddy validate --config /etc/caddy/Caddyfile
Valid configuration
```

### 9. git

提交信息以 `005:` 开头。

## 设计偏差

1. `/me/teams/`、`/me/registrations/` 本轮不做页面；导航仍列出这两项，但标记为不可用（即将开放），避免 404。
2. `SiteSettings.max_game_accounts` 的 `help_text` 去掉了「后续里程碑使用」，因为本轮已经读取该字段。
3. 功能权限菜单挂在 Wagtail「设置」下，和用户/用户组放一起，而不是主侧栏。

## 未完成 / 不同意

无。

## 顺带发现

- 375px 顶栏同时放「个人中心」和「退出」偏挤，标签栏 6 项需要横向滑。能用，若以后要改布局需设计拍板。
- daisyUI 5 的 `tabs-box` / `menu-active` 可用；不要再用已删除的 `input-bordered`。
- 本机 `/usr/bin/git` 仍被 Xcode license 拦住，提交继续用 GitHub Desktop 自带 git。

## 需要确认

无。

## 改动文件

加密：`core/fields.py`、`core/crypto.py`、`core/forms.py`、`core/models.py`、`core/mail.py`、`core/migrations/0003_profile_and_encrypted_smtp.py`、`core/tests/test_crypto.py`、`core/tests/test_mail.py`。

账号资料：`accounts/models.py`、`accounts/ranks.py`、`accounts/forms.py`、`accounts/views.py`、`accounts/urls.py`、`accounts/permissions.py`、`accounts/services.py`、`accounts/wagtail_hooks.py`、`accounts/migrations/0002_profile_and_encrypted_smtp.py`、`accounts/tests/test_ranks.py`、`accounts/tests/test_profile.py`、`accounts/tests/test_me.py`。

初始化与路由：`core/management/commands/init_site.py`、`sjtu_ow/urls.py`。

模板：`templates/me/**`、`templates/components/{account_area,rank_badge}.html`、`templates/wagtailusers/users/edit.html`。

文档：`README.md`、`handoff/STATUS.md`、本报告。
