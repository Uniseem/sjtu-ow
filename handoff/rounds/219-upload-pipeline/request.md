# 219 所有上传走同一条管线

## 背景

218 之后，重写开工前现行站上还剩「先做」里的图片一组（`docs/rewrite-research/12-architecture.md` 11.1、217 review 建议顺序第 1 步的后半）。217 复核发现，除了头像（216 修过）以外，用户传的图原样存、原样公开：

- **07-1（高，暴露面）**：队标 EXIF 坏掉（有些手机、修图软件导出的图本来就不规范），能正常解码，只在 Wagtail 生成缩略图时 `exif_transpose` 抛 `ValueError`。显示这个队标的页面（战队主页、列表、队长管理页、队长个人主页）全部 500；预渲染保留旧文件，首页和战队列表从此停在旧版本
- **07-2 / 02-3（中）**：队标没有像素上限，1.44 亿像素的 PNG 收进来，每种缩略图解码约 430MB，而且每次换队标都排一遍重新生成
- **07-3 / 02-1（中，隐私，已复现）**：队标、后台上传、文章插图的原图原样存在公开的 `/media/original_images/`，文件名从缩略图地址就能推出来，GPS、机型、拍摄时间随图公开（只有头像重新编码）
- **07-4（低）**：Pillow 认得、却没登记 MIME 类型的 23 种格式（QOI、DDS……）改名 `.png` 就过表单，`create_logo` 里 500
- **02-2 / 07-11（中）**：换队标、删队标不删旧图；上传不限次，能填满磁盘
- **02-4（中）**：投稿图片不限次数、不限总量

对应新站的架构不变量 7：「所有上传走同一条管线：先读图头查像素再解码、解码失败即拒、重新编码去掉 EXIF/GPS、原图不公开、每日次数和磁盘配额、替换时删旧文件」。现行站在这一轮里做到这条的 Python 版；Go 版以后照着它的测试写。

## 本轮范围

做：

1. **一个模块 `core/uploads.py`**：`clean_image(uploaded, *, max_pixels, max_side)` → 处理好的 `ContentFile`，失败抛 `UploadError(给人看的话)`。先读图头的尺寸再解码（超像素上限直接拒，不解码）；格式白名单（JPEG、PNG、WebP，按 Pillow 认出来的格式判断，不看扩展名和 MIME）；动图留第一帧；`exif_transpose` 放在 try 里，读不出就拒；重新编码（去掉全部元数据）、长边超过 `max_side`（4096）缩到 `max_side`；文件名换成随机名。头像的 `square_face` 改用它的解码部分，不改它的输出
2. **Wagtail 图片上传表单的基类**：设置 `WAGTAILIMAGES_IMAGE_FORM_BASE` 指向 `core.image_forms.SafeImageForm`，在 `clean_file` 里过 `clean_image`（新上传才处理，编辑已有图不动）。这一条同时管住后台上传（`backoffice/views/images.py`）、编辑器插图（`content/markdown_views.py`）和超管的 `/wagtail/images/`。`WAGTAILIMAGES_MAX_IMAGE_PIXELS` 设成 4000 万，和头像一致
3. **队标**：`teams/forms.py` 的 `clean_logo_file` 也过 `clean_image`（读不出、超像素是字段错误，不是 500）；`create_logo` 放进「队标」集合（现在落在根集合里），换队标和删队标时删旧图（和它的缩略图、文件），**但不删还在别处用着的**
4. **上传限次**：后台上传、编辑器插图、队标，每人每天各有一个上限（成员 30 张、有 `add_image` 权限的内容编辑 200 张，超管不限；数字做成常量），超限给提示，不是 500；限流计数用 `core.ratelimit.over_limit`
5. **历史文件**：已经在库里的原图带着 GPS 的，写一个管理命令 `scrub_originals`（`--dry-run`），逐张重新编码原图、更新宽高和 `file_size`、`file_hash`、删旧文件和缩略图。**命令本轮写好、在测试机上演练，正式站上不跑**，等用户点头

不做：

- 02-5/11-4（选图控件填非数字 500）、02-6、02-7、02-9、02-10、02-11、02-12 这些别的图片条目（217 review 里的低、中，不挡重写）
- 15-2/01-2、13-1、14-2（拖垮全站类）、丢数据类：按重写节奏在这一轮之后逐轮做
- 磁盘总量配额（只做每日次数；总量由 `/healthz` 的磁盘检查兜）

## 任务

1. `core/uploads.py` + 单元测试：好图（JPEG/PNG/WebP、带 EXIF 和 GPS）进去、出来的字节里没有 EXIF 和 GPS、方向转正；坏 EXIF 的 JPEG、带坏 `Raw profile type exif` 块的 PNG 读不出就拒（`UploadError`），不抛别的；超像素的只读头就拒（用 `Image.open` 不触发 `load` 的方式断言没有解码）；QOI 等没有 MIME 的格式拒；动图留第一帧；超长边缩小；文件名随机
2. `SafeImageForm`：后台上传、编辑器上传、`/wagtail/images/add/` 三个入口各一条测试——传带 GPS 的 JPEG，存下的原图字节里没有 GPS；传坏 EXIF 的图，字段错误；超限的拒绝；编辑已有图（不换文件）不重新编码
3. 队标：传坏 EXIF 的 PNG 建队、换队标、删队标都不 500，战队主页、列表、管理页、队长个人主页都 200；换队标后旧图文件和缩略图都删了，旧图在别处用着时不删；队标落在「队标」集合
4. 上传限次：三个入口各一条超限测试
5. `scrub_originals`：造一张带 GPS 的原图，跑命令，原图字节里没有 GPS、宽高和哈希更新、缩略图重新生成时能用；`--dry-run` 什么都不改
6. 每条新规则变异（硬规则 7），写 `handoff/rounds/219-upload-pipeline/mutate.py`
7. 设计：5.2/7.1（队标）、3.5.1（头像一节指过去）、13.10（图片）、16.x 里写这条管线和每日上限；附录 D 记 v7.22

## 验收标准

`bash scripts/remote-check.sh` 整组全绿；变异全部被抓到；推送后 CI 绿。
