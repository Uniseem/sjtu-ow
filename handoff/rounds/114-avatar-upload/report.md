# 114 成员上传头像（先审后显示）（报告）

## 做了什么

1. **设计 v6.11**：细节 2.3 把「以后（用户上传）」换成「上传」一整段（谁能传、文件、处理、先审后显示、一张待审、频率、改用默认头像、谁审、通知、存储清理、注销），细节第 11 节划掉「用户上传头像」；`design.md` 3.5.1、3.8（注销删图、导出含上传记录）、4.3.1（`avatar_upload`）、5.5.1（头像由人审）、10.2（两类新邮件）、12.3.1a（新表）、12.3.1（`avatar` 说明）、13.2.7（文件选择框、`c-faces`）、13.4（三个地址）、14.1、14.2（头像审核）、附录 B（枚举）、附录 C（参数）、附录 D
2. **模型** `accounts.AvatarSubmission`（迁移 0007）：上传人、图片、状态（待审核 / 已通过 / 未通过 / 已撤回 / 已撤下）、原因（复用 AI 审核的类别）、说明、审核人、时间；数据库约束保证一人只有一条待审核。`Feature.AVATAR_UPLOAD`
3. **处理图片**（`accounts/images.py`）：只认 JPEG、PNG、WebP；至少 128×128、最多 4000 万像素（只读文件头就判断，不解码）；按方向信息摆正、从中间裁成正方形、大于 512 缩到 512、重存 WebP（不带原来的 EXIF）；文件名随机；放进新集合「用户头像」（`init_site` 建）
4. **业务**（`accounts/services.py`）：`submit_avatar`（功能权限、每天 5 次、处理、作废上一张待审、排一次提醒）、`withdraw_avatar`、`remove_avatar`、`approve_avatar`、`reject_avatar`、`take_down_avatar`、`forget_uploaded_faces`。换脸一律经过 `user.save()`，显示这个人的页面跟着重新生成；只删「通过上传来的」旧图（演示站脚本写进去的不删）；删图在换脸之后，免得数据库直接置空、跳过信号
5. **前台**：「基本资料」页最上面一块「头像」：现在的头像和待审的新头像并排（新头像也压在这个人的底图上，和换上后一样）、状态说明、上次没通过的原因、上传框、「撤回待审核的头像」「改用默认头像」；被禁止上传的人只看到 4.3.2 的提示。三个只收 POST 的地址 `/me/avatar/`、`/me/avatar/withdraw/`、`/me/avatar/remove/`
6. **后台**「社区 → 头像审核」（`moderation/avatar_admin.py`，内容编辑和超级管理员）：待审核、已通过、未通过、已撤下四个标签带数量；每张大图、上传人、时间、之前被拒几次；通过一键，不通过和撤下要选原因、可加说明；表单回跳只接受站内地址
7. **邮件**（`accounts/notifications.py`，信的格式）：不通过、撤下发给本人（原因、说明、重新上传的链接）；新上传时用缓存占位、10 分钟后由 worker 发一封汇总给审核的人，期间的上传都列进这一封，发出后下一次上传才排新的（`accounts/tasks.py`）。三封都加进邮件样张页
8. **注销和导出**：注销时删本人所有上传的图和记录；导出加 `avatar_uploads`（状态、时间、原因、说明，不含审核人）
9. **样式**：`c-field` 里的文件选择框（按钮和次要按钮一样，原来队标上传框没有样式）；`c-faces`；样张页加了两者；后台审核页的样式放在 `static/css/avatar-review.css`
10. **README**：成员上传头像一条；`init_site` 建四个图片集合
11. **测试**：`accounts/tests/test_avatar_upload.py`（28 条），`core/tests/test_chapter15_audit.py` 的枚举表加两项

## 中途发现的

- 图片说明 `figcaption` 先写成 13px，`test_no_text_is_smaller_than_14px` 拦下，改成 14px
- 附录 B 的枚举由 `test_enum_values_match_appendix_b` 对照，加了功能标识和上传状态
- 审核页回跳地址一开始只判断「以 / 开头」，`//别的网站` 也能过，改用 `url_has_allowed_host_and_scheme`，测试里专门放了这个地址
- 撤下时如果不先清 `user.avatar`，删图会让数据库直接把它置空：头像是没了，但不经过 `save()`、页面不会重新生成。变异第一次没抓到，给测试加上「页面重新生成了一次」

## 命令输出

变异（`mutate.py`，34 处）。第一次漏了「撤下不清头像」（见上），测试补上后整组重跑：

```
baseline green, 24 tests
caught the photo is not turned upright -> test_the_camera_data_is_gone_and_the_picture_stands_up
caught the camera data is kept -> test_the_camera_data_is_gone_and_the_picture_stands_up
caught the picture is not squared -> test_a_small_picture_keeps_its_size_but_is_square
caught big pictures are not shrunk -> test_a_photo_becomes_a_square_webp_of_at_most_512
caught faces are stored as PNG -> test_a_photo_becomes_a_square_webp_of_at_most_512
caught tiny pictures pass -> test_pictures_we_cannot_use_are_refused
caught huge pictures pass -> test_a_huge_picture_is_refused_before_it_is_decoded
caught any format passes -> test_pictures_we_cannot_use_are_refused
caught big files pass the form -> test_the_form_refuses_big_files_and_other_types
caught other types pass the form -> test_the_form_refuses_big_files_and_other_types
caught an upload shows at once -> test_an_upload_waits_for_review_and_changes_nothing_in_public
caught the earlier upload keeps its picture -> test_a_new_upload_replaces_the_one_waiting
caught barred members still upload -> test_someone_barred_from_uploading_can_still_go_back_to_default
caught no daily limit -> test_five_uploads_a_day
caught withdrawing keeps the picture -> test_withdrawing_deletes_the_picture
caught going back to default deletes scripted faces -> test_a_face_put_there_by_script_is_not_deleted
caught approving does not put the face up -> test_approving_puts_the_face_up_and_regenerates_its_pages
caught approving keeps the replaced upload -> test_approving_puts_the_face_up_and_regenerates_its_pages
caught approving deletes a scripted face -> test_approving_keeps_a_scripted_face_it_replaces
caught a rejected picture stays -> test_rejecting_deletes_the_picture_and_tells_the_person
caught nobody is told about a rejection -> test_rejecting_deletes_the_picture_and_tells_the_person
caught a taken-down face stays up -> test_taking_down_a_face_in_use
caught no reason needed -> test_a_decision_needs_a_reason_and_happens_once
caught a decision can happen twice -> test_a_decision_needs_a_reason_and_happens_once
caught anyone in the admin opens the review page -> test_only_reviewers_open_the_review_page
caught anyone in the admin decides -> test_only_reviewers_open_the_review_page
caught the page sends reviewers anywhere -> test_a_reviewer_approves_from_the_page
caught each picture fetches its thumbnail -> test_the_review_page_costs_the_same_however_many_wait
caught each upload mails the reviewers -> test_reviewers_get_one_reminder_for_a_batch
caught one reminder silences the next -> test_the_reminder_lets_the_next_upload_ask_again
caught deleting the account keeps the pictures -> test_deleting_the_account_deletes_every_uploaded_picture
caught the export leaves the uploads out -> test_the_export_lists_the_uploads
caught the waiting picture is not shown to its owner -> test_an_upload_waits_for_review_and_changes_nothing_in_public
caught barred members see the file picker -> test_someone_barred_from_uploading_can_still_go_back_to_default
restored and green; missed: none
```

整组检查（开发服务器停着）：

```
All checks passed!
281 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
```

```
1329 passed in 247.54s (0:04:07)
```

本机走完整流程（开发库，`runserver`，无头 Edge 带登录 Cookie）：给 1 号用户建会话、用官网雾子头像上传一张；「基本资料」页左边是现在的头像、右边「审核中」的雾子；把 3 号用户临时加进内容编辑，后台「头像审核」显示待审核 1 张、通过按钮和不通过的原因下拉；通过后「基本资料」、成员个人主页都换成雾子（压在橙色底图上），后台「已通过」标签里这张标着「正在使用」、有撤下表单。截完把 1 号用户的头像改回原来的（22），删掉上传的图和记录、会话、排队的提醒任务，3 号用户移出内容编辑：

```
{'member_avatar': 22, 'reviewer_added_to_editors': True, 'member_session': '…', 'reviewer_session': '…', 'submission': 1}
tasks removed (1, {'django_tasks_database.DBTaskResult': 1})
22 0 False
```

演示站升级（镜像时间 `2026-10-03T13:23:00+02:00`）：

```
Running migrations:
  Applying accounts.0007_avatar_submission... OK
已确保图片集合：用户头像
全量生成完成：成功 46，失败 0，删除 0；目录占用 1604 KB
{"status": "ok", ...}
302
```

（最后一行是未登录访问 `/me/` 跳到登录页。）演示站登录要 HTTPS，在容器里用测试客户端（模拟 HTTPS）以 2 号演示用户真走了一遍上传和撤回，然后清理：

```
upload: 302 pending WEBP (512, 512) | waiting shown: True | face unchanged: True
withdraw: withdrawn | picture gone: True
cleaned: (1, {'django_tasks_database.DBTaskResult': 1}) | images back to True | records left: 0
```

## 没做 / 未验证

- 拖动选区裁剪：要加前端库（规则 5），现在从中间裁，上传框下写明了
- AI 看图：现在的审核模型只看文字
- 演示站上的浏览器流程：登录要 HTTPS，等你配好反向代理；而且审核要有内容编辑或超级管理员账号
- 待审提醒邮件真实发出：演示站没配 SMTP；本机测试里验证了一封里列出全部待审、10 分钟后发
- 手机宽度、深色模式下的「头像」一块没截图
