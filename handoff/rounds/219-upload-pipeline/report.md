# 219 实现报告

## 结论

完成。所有上传的图走同一条管线（`core/uploads.py`）：先读头查像素、只认 JPEG/PNG/WebP、读不出是提示不是 500、重新编码去掉 EXIF 和 GPS、随机文件名、每人每天限次；队标放进「队标」集合，换了删了旧图一起删；旧原图有 `scrub_originals` 命令。**命令没有在正式站上跑**（等你点头）。头像的 `square_face` 没动（它的输出本来就是对的）。

## 逐条结果

| 任务 | 结果 |
|---|---|
| 1 `core/uploads.py` | `clean_image(uploaded, max_pixels=4000万, max_side=4096)` → `CleanImage`（ContentFile，带宽高），失败抛 `UploadError`（中文提示）。按 Pillow 认出的格式判断，不看扩展名和类型；先读头的尺寸再解码；`Image.load()` 和 `exif_transpose` 都在 try 里；动图留第一帧；统一输出 WebP q90、随机名；已经洗过的（`CleanImage`）直接放行，不洗两遍 |
| 2 Wagtail 表单 | `core/image_forms.py` 的 `SafeImageForm`，`WAGTAILIMAGES_IMAGE_FORM_BASE` 指向它，`WAGTAILIMAGES_MAX_IMAGE_PIXELS` 设成 4000 万。后台上传、对话框上传、编辑器插图、`/wagtail/images/` 四个入口各有一条测试；编辑已有图（不换文件）不动文件 |
| 3 队标 | `TeamForm` 的 `clean_logo_file` 过 `clean_logo`（字段错误，不是 500），`create_logo` 放进「队标」集合（`content.services.ensure_team_logo_collection`）；`update_team` 在换掉、删掉旧队标后排 `discard_logo`（只删「队标」集合里、没有别的队在用的）。三个调用点（建队、管理页提交、自动保存）都覆盖 |
| 4 限次 | `over_daily_limit(user)`：成员 40 张、内容编辑 300 张、超管不限，计数用 `core.ratelimit.over_limit` 一天一桶；Wagtail 表单和队标表单共用同一个计数 |
| 5 `scrub_originals` | `--dry-run`、`--collection`（可重复）、`--all`。默认只看「投稿图片」「队标」和每支队的队标里**带 EXIF 的**，重新编码原图、更新宽高和哈希、删旧文件；缩略图地址不变；还在共用集合里的队标搬进「队标」。读不出的报告出来、其余继续 |
| 6 变异 | `handoff/rounds/219-upload-pipeline/mutate.py`，24 处，全部被抓到 |
| 7 设计 | v7.22：13.10 加「上传的图片」一条，7.1 队标一行，附录 D；README、AGENTS 跟着改 |

新增测试：`core/tests/test_upload_pipeline.py`（23 条，函数 + 四个入口 + 限次）、`teams/tests/test_logo_pipeline.py`（11 条，含 `transaction=True` 的删旧图）、`core/tests/test_scrub_originals.py`（5 条）。

## 验收输出

整组（`bash scripts/remote-check.sh`，测试机，退出码 0）：

```
== ruff   All checks passed! / 437 files already formatted
== pytest 2163 条测试分成 4 片
分片 1：541 passed in 69.08s   分片 2：541 passed in 67.29s
分片 3：541 passed in 64.83s   分片 4：540 passed in 59.18s
== 迁移   No changes detected
== 生产配置 System check identified no issues (0 silenced).
== Docker 镜像 构建成功：dd31612aa815
== 全部通过
```

变异（测试机）：基线全绿，**24 处变异全部被抓到**，改回后基线全绿。

写测试时踩到的两件事（都已写进 AGENTS「已知的坑」）：

1. **Wagtail 8 删图片文件不是提交后马上删，而是排一个任务让 worker 去删**（`wagtail.tasks.delete_file_from_storage_task`）。第一版测试断言「文件马上不在了」红了。改成断言任务排了、再调 `.func(*args)` 执行，之后文件确实没了
2. **「读不出」的历史图没法在测试里造出来**：截断的 JPEG 在 `Image.objects.create` 读宽高时就抛错。改成建好行之后把磁盘上的文件换成垃圾

## 设计偏差

无（设计 v7.22 先写后做）。

## 未完成 / 顺带发现 / 需要确认

1. **正式站上还没跑 `scrub_originals`**。步骤在 README「图片上传（219 起）」：先 `--dry-run` 看有几张带位置的，再真的处理，之后 `prerender` 一次。要登录正式站，等你点头。正式站才上线几天，数量应该不多
2. **后台改战队队标（`backoffice` 的战队编辑页，从图片库里选）不会删旧队标**：那条路不经过 `update_team`。旧图留在「队标」集合里，只是占点磁盘，不影响显示和隐私。留给下一轮
3. 这条管线挡在**表单层**。脚本里直接 `Image.objects.create(file=…)`、管理命令、超管在 shell 里，不经过它。这是有意的（官方封面、演示图是站长自己传的、要原样），写进了 AGENTS
4. 217 review 里和图片有关、本轮**没做**的：02-5/11-4（选图控件填非数字 500）、02-6、02-7、02-9、02-10、02-11、02-12（大多是低）。不挡重写
5. 上一轮留下的核对：Wagtail 的 `/wagtail/password_reset/` 等三个地址，GET 和 POST 都是 404（`WAGTAIL_PASSWORD_MANAGEMENT_ENABLED = False` 起了作用），不用另外挡
6. **行为变化请知道**：站长在后台上传封面、图片库的图，也会被重编码成 WebP（q90）、长边最多 4096。对封面够用，但原图不再留着；站长要保留原图的话，得改成「超级管理员上传不重编码」，这是设计决定，我没替你做

## 改动文件

`core/uploads.py`、`core/image_forms.py`、`core/management/commands/scrub_originals.py`（新）；`teams/images.py`、`teams/forms.py`、`teams/views.py`、`teams/services.py`、`content/services.py`、`sjtu_ow/settings/base.py`；三份新测试；`docs/design.md`（v7.22）、`README.md`、`AGENTS.md`、`handoff/STATUS.md`、本轮 `request.md`、`report.md`、`review.md`、`mutate.py`。
