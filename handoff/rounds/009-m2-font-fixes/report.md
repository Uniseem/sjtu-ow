# 009 实现报告

> 本轮同样由 Claude 实现（用户外出，按「自己 review 然后继续」的交代推进）。

## 结论

008 自查出的 4 个必须修、4 个建议修全部改完，157 个测试通过。核心是**把「跟随正文」的口径统一到一处**（`css.used_pairs()`），以及**把文件清理补齐**（旧原始文件立即删、被替换的分片延迟一天删）。

## 逐条结果

### T1 文件清理

- **A1**：`add_face_from_bytes()` 在存新文件之前先 `original_file.delete(save=False)`。实机验证见下。
- **A4**：`add_google_faces()` 在覆盖 `slices` 之前，把这个字重不再使用的旧分片删掉。
- **B1**：重新切片成功后，被替换的分片不再立刻删除，改为 `retire_slice_files()` —— 用 `django-tasks` 排一个一天后执行的 `delete_retired_font_slices`，到期时**再确认没有任何字重引用**这些路径才删（和旧样式表保留一天一致）。

### T2 「跟随正文」口径统一

- **A2**：`services.is_face_in_use()` 改成 `(family_id, weight) in used_pairs(ordered_rules())`，和生成样式表用同一套解析；`delete_face()` 末尾调用 `regenerate_font_css()`，删完字重样式表立刻跟上。
- **A3**：`run_face_processing()` 用同一个 `is_face_in_use()`，所以「先设正文字体、再补传 Bold」处理完会自动重新生成样式表。

### T3 后台小改

- **B2**：`create_family()` 包了一层重试（最多 5 次），`css_name` 撞唯一约束时重新取号，不再 500。
- **B3**：字体库列表和详情页显示磁盘占用（原始文件 + 当前分片）。
- **B4**：排版设置的字体下拉除了「有处理完成字重的字体」，还包含当前区域已选中的字体，字重被删光后界面上仍看得见自己选的是什么；保存时的校验没放松。

## 验收输出

### 1. 检查与测试

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
148 files already formatted

$ uv run python -m pytest -q
157 passed in 9.71s

$ uv run python manage.py makemigrations --check --dry-run
No changes detected
```

本轮新增 9 个测试：重复上传删旧原始文件、「跟随正文」用到的字重算在用、后台拒绝删除该字重、补传字重后样式表自动更新、被替换分片延迟删除 + 仍被引用时不删、延迟任务的排期、`css_name` 撞车重试、下拉保留已选字体、磁盘占用统计。

### 2. A1 实机：同一字重传两次

```
A1 第一次上传: fonts/5/original/SourceHanSansCN-Regular.otf
A1 第二次上传: fonts/5/original/SourceHanSansCN-Regular-v2.otf
A1 磁盘上的原始文件: ['SourceHanSansCN-Regular-v2.otf']
```

修之前两个文件都会留着（008 复核里实测过）。

### 3. A3 + A2 实机：正文自定义 400、一级标题跟随正文 700

补传 Bold（字重选「自动识别」）：

```
补传前的样式表: /media/fonts/css/fonts.f5853e3db069.css
自动识别出的字重: 700 pending
700 处理完：ready 66 片，用时约 40s
补传后的样式表: /media/fonts/css/fonts.182649d7cde0.css → 自动换了新哈希
样式表里的 @font-face 条数: 132
含 700 字重: True
```

再删这个 700 字重：

```
is_face_in_use(700) = True
HTTP 200 | 700 还在: True
提示: 正在被排版设置使用，请先在排版设置里换成其他字重。
```

### 4. B1 实机：被替换的分片延迟删除

把同一个 400 字重换成另一个文件（内容不同，66 片全换）：

```
替换前 400 的分片数: 66
处理结果: ready | 换掉的分片数: 66
换掉的分片现在还在磁盘上: True
延迟任务: core.tasks.delete_retired_font_slices | run_after: 2026-09-17 10:17:19+00:00
任务里带的路径数: 66
```

到期逻辑手动执行一次（相当于一天后 worker 跑这个任务）：

```
到期任务里的路径数: 66 | 执行前还在磁盘: 66
手动执行到期逻辑，删除: 66 | 执行后还在磁盘: 0
```

### 5. B3 后台显示磁盘占用

字体库列表（后台截图对应的文字）：

```
名称        样式表字体名   来源  授权      字重                  磁盘占用   预览
009 思源黑体  sjtu-font-1   上传  开源授权  400（可用）、700（可用）  27.8 MB   上海交通大学守望先锋社区 SJTU Overwatch 2026 钻石 3 · Genji#51234
```

### 6. 回归

```
/                                200
/news/                           200
/news/m2-first-guide/            200
/about/                          200
/submit/                         200
/healthz                         200
/admin/settings/fonts/           302   （未登录，符合预期）
/admin/settings/typography/      302
```

前台首页仍然引用当前样式表：`fonts/css/fonts.14783b0dc312.css`（补传字重后自动换的那份）。

### 7. docker / caddy

```
Successfully built 21b7a094e383
Successfully tagged sjtu-ow:ci

Valid configuration
```

### 8. 验收数据清理

字体、验收账号、延迟任务记录、多余样式表都清掉了；排版设置恢复默认（正文和代码区系统字体，其余跟随正文）。`media/` 现在 136KB，只剩默认样式表。

## 设计偏差

无。A1–A4 都是实现向设计 v1.5.5 对齐（12.4.5「`mode = inherit` 时指正文字体的字重」）。B1 的「旧分片保留一天」和设计里「旧样式表保留一天」同源，已经在 13.12.4 写过保留策略，这里只是把分片也纳入同一条规则——**这一点需要在下一轮把设计 13.12.2 补一句**（我会在 010 的文档更新里一起改，避免本轮又动文档又动代码）。

## 未完成 / 不同意

1. 磁盘占用只统计**当前**分片和原始文件，不含「已退休但还没到期删除」的那一代分片，所以刚重新处理完的一天内，实际占用会比显示的多一倍。要不要把退休分片也算进去，等用户回来定。
2. A4（Google Fonts 重新导入删旧分片）只做了代码层面的修改和单元测试，**没有实机验证**——本机 DNS 把外网解析到 `198.18.0.0/15`，后台那条路径过不了 SSRF 检查（008 报告里说明过）。

## 顺带发现

- `django-tasks` 的数据库后端模块是 `django_tasks_db`（不是 `django_tasks_database`），任务行在 `DBTaskResult`，参数存在 `args_kwargs` 里。写测试时记一下。
- `delete_unreferenced_slices()` 现在会扫全部 `FontFace` 的 `slices`。字体数量少时无所谓，将来字体多了可以只扫同一个字体。

## 需要确认

同 008 报告里那两条（字体体积预算、退休分片是否计入磁盘占用），不阻塞。

## 改动文件

`core/fonts/services.py`、`core/fonts/forms.py`、`core/fonts/admin_views.py`、`core/tasks.py`、`core/templates/core/fonts/{index,detail}.html`、`core/tests/test_fonts.py`、`handoff/rounds/009-m2-font-fixes/*`、`handoff/STATUS.md`。
