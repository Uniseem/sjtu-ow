# 217 复核 02：图片与头像

范围：`backoffice/views/images.py`（图片库、选图对话框、上传 JSON 接口、按张的改删权限、集合）、`backoffice/widgets.py` 的选图控件、`moderation/avatar_admin.py`、`accounts/images.py` 和头像上传视图、`teams/images.py` 和队标上传、`content/markdown_views.py` 的上传、Wagtail 图片设置、`core/avatars.py`、`core/covers.py`、`content/signals.py` 里图片相关的信号、`deploy/Caddyfile` 的 `/media/`。

**复现情况**：复现脚本 `findings/02-repro_tests.py`（断言的是缺陷的表现，绿 = 复现）在测试机上跑了一次（`bash scripts/remote-check.sh run uv run pytest -q -s -p no:cacheprovider handoff/rounds/217-second-review/findings/02-repro_tests.py`），写报告时才排到。命令末尾接了 `| tail -80`，前面几条测试打印的数字被截掉了，只剩汇总和 02-7 的输出；协调人要求收尾，没有重跑。真实输出：

```
[02-7] delete by 内容编辑 -> 302; team.logo=None; prerender requests: [('request_page', ('/members/',)), ('request_page', ('/',)), ('request_page', ('/members/',))]
F
...
DecompressionBombWarning: Image size (120000000 pixels) exceeds limit of 89478485 pixels, could be decompression bomb DOS attack.
FAILED handoff/rounds/217-second-review/findings/02-repro_tests.py::test_02_7_deleting_a_used_picture_regenerates_nothing
1 failed, 7 passed, 3 warnings in 5.44s
```

一共收集到 8 条（脚本最后加的 `test_02_8` 不在那次的快照里）。带硬断言的 `test_02_1`（两条路都在原图里读到 GPS 纬度）、`test_02_2`（`team.logo` 为空，库里还有 ≥6 张队标）、`test_02_3`（QOI 改名 PNG → 500）都绿了，对应本文的 02-1、02-2、02-8 标「已复现」。`test_02_4`、`02_4b`、`02_5`、`02_6` 只打印不断言，数字被截掉，按「已核对代码」/「推测」记。02-7 的说明见那一条。

## 发现

### 02-1 中：原图的 EXIF（含 GPS）原样存进公开目录，地址能从缩略图推出来

- **位置**：`teams/images.py:6-23`（队标原样存进 Wagtail）、`backoffice/views/images.py:94-111`（`_upload_one`）、`content/markdown_views.py:24-60`（正文上传）；`deploy/Caddyfile:93-98`（`/media/*` 全部公开，只有 `/media/fonts/*` 例外）；Wagtail `images/models.py:331-355`（`original_images/<原文件名>`）、`:878-894`（缩略图文件名 = 原文件名的前 20 来个字符 + 裁切参数）
- **问题**：头像那条路专门重新编码去掉了拍摄地点（细节 2.3「照片里的拍摄地点、设备等信息不会留在服务器上」），但队标、后台上传、正文插图都是原文件原样落盘，项目里没有任何去 EXIF 的地方（`grep -i exif` 只有头像）。缩略图本身不带 EXIF（Pillow 12 存 WebP/JPEG 只看 `encoderinfo`），但原图在 `/media/original_images/` 下由 Caddy 直接对外，文件名就是上传时的文件名。缩略图地址 `/media/images/IMG_20261001_1234.2e16d0ba.fill-400x400.format-webp.webp` 已经把原文件名带出来了，扩展名只有 jpg/jpeg/png/webp 四种可猜。
- **失败场景**：队长用手机直接拍了一张队徽照片当队标（或者投稿者把活动现场照片插进正文）；任何访客从战队页的 `<img src>` 取文件名，拼 `/media/original_images/IMG_20261001_1234.jpg`，下载到带 GPS 和机型的原图——宿舍、家里拍的照片就是住址。任何验证过邮箱的成员都能建战队、都能投稿，所以这不只是管理员的事。
- **怎么验证**：`02-repro_tests.py::test_02_1_originals_keep_gps_and_the_address_is_derivable`：用 POST `team_create` 上传一张带 GPS EXIF 的 JPEG，读 `team.logo` 原文件的 GPS IFD，打印原图和缩略图地址；同样用投稿者走 `image_chooser_upload`。在部署好的站点上：`curl -sI https://站点/media/original_images/<缩略图里的前缀>.jpg`。
- **状态**：已复现（测试机上 `test_02_1` 绿：队标和投稿者上传的原图里都读到了 `GPSLatitude`；打印的地址被 `tail` 截掉。「从缩略图推出原图地址」是按 Wagtail 源码核对的，没在部署好的站点上 curl）

### 02-2 中：换队标、删队标都不删旧图，次数也不限，一个队长就能把盘写满

- **位置**：`teams/views.py:221-227`（自动保存）、`:258-264`（整表提交）、`teams/services.py:177`（`team.logo = logo`，旧的那张没人管）；`_drop_unused_logo`（`teams/views.py:142-145`）只在保存失败时删新图
- **问题**：每次选文件都 `create_logo` 新建一张 Wagtail 图片（根集合，原图 ≤5 MB + 若干缩略图），换上以后旧图留在库里和磁盘上；勾「删除队标」也只是把外键置空。没有每天的次数限制（头像有 `AVATAR_UPLOADS_PER_DAY = 5`，换头像还会删旧图，细节 2.3「存储清理」；队标两样都没有）。战队管理页 v7.11 起「选好文件就上传换上」，脚本连发自动保存请求就能一直写。
- **失败场景**：一个队长（任何成员都能建队）脚本循环往自己的战队管理页 POST 5 MB 的 PNG：每次 5 MB 进 `media` 卷，1 万次 50 GB。正式站的盘 186 时剩余 31%（约 49 GB），`/healthz` 磁盘检查（剩余 >20%）先报 503，再往后备份、SQLite 写入失败。正常使用下也会慢慢攒孤儿图：内容编辑在图片库里看到一堆「XX 队标」不知道哪张还在用。
- **怎么验证**：`test_02_2_replaced_logos_are_never_deleted`：建队后自动保存换 5 次队标、再勾删除，`team.logo` 为空但标题以「队标」结尾的图片还有 6 张。
- **状态**：已复现（测试机上 `test_02_2` 绿：自动保存换 5 次再勾删除后 `team.logo` 为空，标题以「队标」结尾的图片 ≥6 张）

### 02-3 中：队标没有像素上限，后台上传用的是 Wagtail 默认的 1.28 亿；缩略图在请求里同步生成

- **位置**：`teams/forms.py:72-84`（只查字节数和格式）、`teams/images.py:12-13`（Willow 只读文件头）；`sjtu_ow/settings/base.py:324-329`（没设 `WAGTAILIMAGES_MAX_IMAGE_PIXELS`，Wagtail 默认 128,000,000）；生成缩略图的地方：战队卡、战队页、首页「战队」区块（`{% image team.logo fill-400x400 %}` 等）、`backoffice/views/images.py:61-62`（图片库一页 48 张）、`:253`（对话框上传当场生成）、`content/markdown_views.py:60`
- **问题**：头像设计专门定了「最多 4000 万像素（防止解压炸弹）」（细节 2.3），队标却只靠 Django `ImageField` 里 Pillow 自己的闸：超过 8900 万像素只是警告，到 1.79 亿才拒。一张 12000×10000 的纯色 PNG 只有一百多 KB，远在 5 MB 以内；解码成 RGB 要 360 MB 左右，Wagtail 裁切、转 WebP 时再复制。第一次显示时由 gunicorn 进程或 worker（预渲染首页、战队列表、战队页）同步解码；进程被 OOM 杀掉的话缩略图永远存不下来，每次渲染都重来。后台这边：投稿者（任何验证过的成员）一次能传 50 张 1.2 亿像素的图进「投稿图片」，所有投稿者打开图片库或选图对话框都会触发这 48 张的同步解码，单个请求远超 gunicorn 默认的 30 秒超时，worker 被杀后下一个人再来一遍。
- **失败场景**：成员建一支队、传一张 1.7 亿像素的「队标」；首页的「最新战队」和 `/teams/` 每次生成都要吃掉几百 MB 内存、好几秒，容器没有内存上限（`deploy/docker-compose.yml`），正式站同机还有 WordPress 等别的服务。
- **怎么验证**：`test_02_5_pixel_bomb_logo`：用逐行压缩造的 12000×10000 PNG 建队，量一次 `fill-400x400` 的耗时和 `ru_maxrss` 涨幅；同一个文件让投稿者走 `image_chooser_upload`，看是否 200 和用时。
- **状态**：已核对代码（Pillow 的阈值和 Wagtail 的默认值核对过源码。测试机上 `test_02_5` 跑完没报错，日志里有 `DecompressionBombWarning: Image size (120000000 pixels)`，说明 1.2 亿像素的图过了队标表单、被解码了；内存、耗时数字被 `tail` 截掉了）

### 02-4 中：「投稿图片」的上传没有次数和总量限制

- **位置**：`backoffice/views/images.py:114-146`（一次最多 50 个文件，每个 5 MB）、`:236-254`（对话框上传）、`content/markdown_views.py:24-60`；`core/ratelimit.py` 在这三处都没用
- **问题**：`init_site` 让「投稿者」组（每个验证过邮箱的成员都在里面）能往「投稿图片」加图。三个上传入口都不调 `over_limit`，单个请求最多写 250 MB，原图永远不清（没有被引用的图不会过期）。评论、头像、建队、注册都有频率限制，唯独这里没有。
- **失败场景**：一个刚注册的号在 `/admin/images/upload/` 循环提交 50 张 5 MB 的噪点 PNG，约 200 次就把正式站剩余的盘写到 `/healthz` 报 503，再往后备份失败、数据库写不进去。和 02-2 是同一类问题，入口不同、门槛更低。
- **怎么验证**：读代码可见；在测试机上可以照 02-2 的写法循环 POST，看 `media/original_images/` 的大小。
- **状态**：已核对代码

### 02-5 低：选图控件拿到不是编号的值就 500；后台不在乱填测试的范围里

- **位置**：`backoffice/widgets.py:46-51`（`get_image_model().objects.filter(pk=value)`，`value` 直接取自表单提交的值）；用到它的地方：`ArticleForm.cover`（`backoffice/forms.py:168`）、`TournamentForm.cover`（`:464`）、后台 `TeamForm.logo`（`:695`）、全站设置的图片字段（`:834`）
- **问题**：表单校验没通过、整表重新渲染时，控件用提交的原值查库：`cover=abc` → `ValueError: Field 'id' expected a number`，500。`ModelChoiceField` 自己会把 `abc` 当成「选项无效」，炸的是重新渲染这一步。`core/tests/test_garbage_input.py` 的 `PROJECT` 不含 `backoffice.`，`POSTS` 里也没有 `cover`、`logo` 这类字段，所以 166/167 的乱填扫描从没走到后台表单。
- **失败场景**：投稿者（任何成员）在不开脚本或绕开脚本时向 `/admin/articles/new/` 提交 `cover=abc` → 500。要用脚本才填得出这种值，所以是低。
- **怎么验证**：`test_02_4_a_garbage_cover_is_a_500`（不带 `X-Autosave`），`test_02_4b_garbage_cover_on_autosave`（带头，看自动保存这条路是不是只报字段错误）。
- **状态**：已核对代码（`test_02_4`、`02_4b` 在测试机上跑了，但只打印、不断言，打印被截掉了）

### 02-6 低：选图控件把任意编号的图片标题、缩略图回显给看不到它的人

- **位置**：`backoffice/widgets.py:46-58`、`backoffice/templates/backoffice/widgets/image_picker.html:4,7`
- **问题**：`image_field` 的查询集正确地限在「能选的图 + 原来那张」，但表单校验没通过时，控件按提交的编号把图片**不经权限**取出来，显示它的标题，还当场生成并输出缩略图地址。图片编号是连续的。
- **失败场景**：投稿者向 `/admin/articles/new/` 提交 `cover=1`、`2`、`3`…（标题留空，让表单必定不通过），逐个看到超管、内容编辑放在别的集合里的图片标题和缩略图，比如还没公布的赛事海报、首屏图备选。缩略图文件本身在公开的 `/media/images/` 下，拿到地址就能看。
- **怎么验证**：`test_02_8_the_picker_echoes_a_picture_the_writer_may_not_see`（选图对话框里没有，表单回显里有）。
- **状态**：已核对代码（这条是后加进脚本的，排队时的快照里可能没有）

### 02-7 低：删一张正在用的图，不刷新任何静态页

- **位置**：`backoffice/views/images.py:194-206`；`content/signals.py:199-202`（`post_delete` 只在图属于默认封面、默认头像图库时 `request_all_soon`）；外键全是 `SET_NULL`（`teams/models.py:25-31`、`accounts/models.py:99-105`、`tournaments/models.py:36-40`、`content/models.py:275-278`、`core/models.py:84-145`）
- **问题**：Django 的 `SET_NULL` 是一条 SQL 更新，不调各模型的 `save()`，战队、文章、赛事、用户、全站设置的刷新信号都不会触发。Wagtail 在事务提交后删掉原图和缩略图文件，预渲染的首页、战队页、文章页还指着被删的 `/media/images/...`，坏图一直挂到次日 04:15 的全量 `prerender`。能删的人：内容编辑（根集合的 delete，含「用户头像」里的头像、根集合里的队标）、投稿者删自己传的图（「投稿图片」里的图所有投稿者都能选作封面，删了别人的文章封面跟着没）。删除确认框写「用到它的文章、横幅会变成默认图」，静态页上实际是坏图。另外内容编辑在图片库里直接删头像，绕过了「撤下」：本人收不到信、记录还是「已通过」。
- **失败场景**：内容编辑在图片库清理「没用的」队标，删到一支队正在用的；战队页、`/teams/`、首页的预渲染页上队标变成破图，到第二天凌晨才恢复。
- **怎么验证**：`test_02_7_deleting_a_used_picture_regenerates_nothing`：把 `core.prerender` 的四个请求函数换成记录器，内容编辑删队标，`team.logo` 变空、记录为空。
- **状态**：已核对代码。测试机上这条是红的，但红在脚本：`calls.clear()` 放在了建内容编辑账号**之前**，记录到的三条 `('/members/',)`、`('/',)`、`('/members/',)` 是建这个账号（验证邮箱、进组）触发的成员页刷新；删图以后**没有**请求战队页 `/teams/<pk>/` 或 `/teams/`，`team.logo=None` 确认外键被置空。结论和代码一致，脚本要把 `calls.clear()` 挪到 `force_login` 之后再跑一次

### 02-8 低：队标传 Pillow 认得、Willow 不认得的格式就 500

- **位置**：`teams/forms.py:72-84`（`content_type and content_type not in LOGO_TYPES`）、`teams/images.py:12`（`WillowImage.open`）；Django `ImageField.to_python` 把 `content_type` 设成 `Image.MIME.get(format)`
- **问题**：Pillow 里有二十多种格式没注册 MIME（QOI、DDS、MSP、SUN、SPIDER、IM、BLP……），Django 给它们的 `content_type` 是 `None`，`clean_logo_file` 只看扩展名，扩展名写 `.png` 就放行。之后 Willow 用 `filetype` 猜格式，认不出来就抛 `UnrecognisedImageFormatError`，`team_create`、`team_manage`（含自动保存）都没接，500。（头像那条看 `picture.format`，没有这个问题。）
- **失败场景**：把一张 QOI 改名 `logo.png` 当队标上传 → 500；自动保存这条路上，`autosave.js` 失败后会按 212 的退避规则重试。
- **怎么验证**：`test_02_3_a_qoi_logo_named_png_is_a_500`。
- **状态**：已复现（测试机上 `test_02_3` 绿：用 `Client(raise_request_exception=False)` POST `team_create`，带一张改名 `logo.png` 的 QOI，返回 500）

### 02-9 低：「连图片一起审核」开关什么都不做

- **位置**：`core/models.py:237-241`（`moderation_image_enabled`，说明写「开启后投稿里的图片也送审，费用更高」）、`backoffice/forms.py:783`（后台设置页上有这个框）；全仓库除迁移和一条默认值测试外没有地方读它
- **问题**：设计 5.5.1 表「图片（队标、封面、投稿图片）……默认不送审，可以在后台开启」、附录的设置表也列着它，但没有任何代码按它送审。站长打开后以为图片在审，其实没有。按 AGENTS「找以后再接的占位」，这是又一处没人回来接的。
- **怎么验证**：`grep -rn moderation_image_enabled --include=*.py . | grep -v migrations`。
- **状态**：已核对代码

### 02-10 低：几个有名字的集合改名、删除没有防护，改了以后功能悄悄失效

- **位置**：`backoffice/views/images.py:292-336`（只挡根集合）；按名字找集合的地方：`content/services.py:314-322`（投稿图片）、`:355-364`（用户头像）、`core/covers.py:21-26`（默认封面、默认头像）、`core/avatars.py:21,38-40`（坦克、输出、支援三个子文件夹）
- **问题**：超管把「投稿图片」改了名或（空的时候）删掉，下一次上传会由 `ensure_submission_image_collection` 按名字新建一个**没有任何组权限**的「投稿图片」（权限行跟着旧集合级联删掉或留在改名后的那个上），所有投稿者的正文插图从此 403「你没有上传图片的权限。」，直到有人重跑 `init_site`。「默认封面」「默认头像」改名后图库直接变空，集合保存不触发刷新，静态页上照旧是原来的图，到夜间全量生成才一起变；三个位置文件夹改名后按位置挑头像失效，没有提示。
- **失败场景**：超管觉得「投稿图片」不好听，改成「成员投稿」。
- **怎么验证**：读代码可见；测试里把集合改名后让投稿者 POST `content:markdown_upload`。
- **状态**：已核对代码

### 02-11 低：投稿者的图片库里，别人传的图点进去是 403

- **位置**：`backoffice/templates/backoffice/content/images.html:21`（每张图都链到 `image_edit`）；`backoffice/views/images.py:153-154`
- **问题**：投稿者能看到「投稿图片」里所有人的图（能选），但只能改删自己的。列表不分，每格都是编辑链接，点到别人的图就是 403 页。210 留的「后台列表页模板的按钮是否按权限隐藏」在这一页的答案就是没隐藏。
- **状态**：已核对代码

### 02-12 低（推测）：多图 JPEG 被头像和队标当成「不是 JPG」拒掉；16 位灰度 PNG 的转换在 `try` 外面

- **位置**：`accounts/images.py:36-37`、`:53-54`；`teams/forms.py:80-84`
- **问题**：带 MPF 多图扩展的 JPEG（立体相机、部分手机的人像或深度图；Ultra HDR 那种 Pillow 已经单独当 JPEG）被 Pillow 认成 `MPO`。头像那条报「头像只支持 JPG、PNG 或 WebP。」，队标那条得到 `image/mpo` 也被拒，而同一个文件走后台上传（Wagtail 用 `filetype` 判断，认成 jpg）是收的。另外 `picture.convert(mode)` 在 `try` 外面（216 只把 `exif_transpose` 挪了进去），`I;16` / `I` 模式的 16 位灰度 PNG 要是转 RGB 时抛异常，就是 500 而不是「读不出这张图片」。两件都没确认：哪些手机实际产出 MPO 不清楚；Pillow 12.3 是否支持 `I;16 → RGB` 没验。
- **怎么验证**：`test_02_6_avatar_odd_but_real_files`（打印 MPO 头像、MPO 队标、I;16 和 I 两种 PNG 的结果）。
- **状态**：推测

## 查过没问题

- **按张的改删守卫**（210 B3）：`image_edit` / `image_delete` 都先 `user_has_permission_for_instance`，213 补了用投稿者测的 `backoffice/tests/test_image_guards.py`。自动保存这条路也在守卫后面。改集合只能改到自己有 add 权限的集合（`ImageEditForm` 的查询集）
- **门**：图片各页都套了 `placed("content", "images")`，集合三页另加 `allowed=access.is_superuser`；`image_delete`、`image_chooser_upload`、集合改名删除都是 `require_POST`
- **跨集合**：列表、对话框按 Wagtail 的集合策略过滤（`instances_user_has_any_permission_for`）；对话框上传按 `collections_for(user, "add")` 过滤集合编号，`as_id` 挡住乱填；`image_field` 的查询集只多放「原来那张」，`current` 取自对象本身，不取自提交的值（02-6 的问题只在重新渲染的回显上）
- **格式**：`WAGTAILIMAGES_EXTENSIONS` 只有 jpg/jpeg/png/webp，没有 SVG、GIF、HEIC/AVIF（Willow 虽然导入了 `pillow_heif`）；Wagtail 的表单核对扩展名和实际格式；头像看 Pillow 识别出的格式，不看扩展名
- **头像**：解码前按文件头查 4000 万像素和 128 边长；动图只取第一帧；216 把 `exif_transpose` 挪进 `try`；重新编码成 WebP，随机文件名，不带 EXIF；每天 5 次；换头像、改用默认、撤下、注销都删本人上传的旧图（`uploaded_face_ids` 只认上传记录，脚本放的头像不删）；撤下检查「这张还在用」、原因要在类别里、`next` 带 `require_https`（216 F6）；停用账号不显示自传头像（216 A12）
- **缩略图不带 EXIF**：Pillow 12.3 存 WebP、JPEG 只看 `encoderinfo` 里的 `exif`，Willow 不传
- **删除图片时的文件**：Wagtail 在事务提交后删原图和各缩略图文件；图片外键全是 `SET_NULL`，没有 `PROTECT`，删图不会 500
- **默认头像、默认封面图库**：按编号取模，图库里的图进出、删除都触发全量刷新（`content/signals.py`）
- **集合删除**：根集合不能删、不能改名；有子集合或图片的不能删
- **坏输入**：列表的 `page`、`collection`、`q` 都有处理（`get_page`、`as_id`、截 50 个字）；头像审核的 `status`、`page` 乱填会退回默认

## 没来得及看

- 复现脚本里只打印的那几条（02-3 的内存、耗时，02-5 的状态码，02-12 的 MPO、16 位 PNG）：输出被 `tail -80` 截掉，没有重跑；02-6 的 `test_02_8` 不在那次的快照里
- Wagtail 的 `/documents/`（`wagtaildocs_urls` 挂在公开地址上）：哪些组能传文档、HTML 文档会不会同源打开
- 被撤下的头像缩略图在 Caddy 的一年 `immutable` 缓存下，前面要是有 CDN 会不会继续可见
- `journey.py` 没跑；图片页一次传多张、对话框翻页和上传失败提示在浏览器里的表现（196 留下的）
- 账号注销时，本人传进「投稿图片」的图和建队时传的队标怎么处理（设计 3.8 的清单没有逐条对）
