# 205 自动保存（中）：文章和网站页面存草稿（报告）

## 做了什么

用户 10-05：「继续做 205」。设计 13.17 写给「203」的一半拆成两轮（203、204 插进了用户新提的两件事），205 做有草稿的内容（设计 v7.9）。

1. **存草稿的机制**（`content/drafts.py`）：
   - `save_draft`：改过的页面存成最新的草稿修订。同一个人 30 分钟内接着改，覆盖自己的上一份草稿（Wagtail 自带的 `overwrite_revision`），不一个自动保存刷一份修订；别人接着改、上一份已经是发布的那份或排了定时上线、隔了半小时，另起一份。操作记录照 202 的做法，30 分钟内合成一条
   - `start_article`：新文章第一次改动就建好（草稿），标题、分类空着也存。页面那一行没有标题存不进去，先写「（无标题）」占着，草稿里的标题是空的；发布时换成真的
   - 迁移 `content/0011`：文章的分类在数据库里允许空。模型上仍是必填，发布时 Wagtail 整体校验，没分类发不出去
   - 草稿不触发 AI 巡查和静态页，只有发布触发（原来就是这样，查过信号）
2. **文章**：写文章、改文章的表单改成自动保存（`data-autosave`），「保存草稿」按钮只在没有脚本时出现，「发布」照旧是按钮、发布时才查必填。新文章第一次保存后页面地址换成编辑页，「预览草稿」链接跟着出来。列表里没标题的写「（无标题）」（页面那一行占位的标题），没分类的写「未选分类」
3. **网址片段跟着标题走**：没发布过、网址还是按标题自动生成的文章，网址跟着标题变；编辑在网址框里改过的不跟；发布过的不变；空着照旧按标题生成。原来网址在第一次保存时定下，改成自动保存以后打第一个字就定死了。服务器改了网址时，回的 JSON 里多一个 `values`，页面上的网址框跟着改（`autosave.js`），下一次保存不会被当成「编辑改了网址」
4. 文章表单的「存的时候补上网址和作者」从 `save()` 里拿出来成了 `finish()`，部分保存时也走它
5. **网站页面**（关于我们、两份协议）：同上，改了存草稿，「发布」才上线
6. **首页置顶、资讯栏目介绍**：原来点保存就直接上线，改成改了存首页、栏目的草稿，「发布」才上线；编辑页右边写状态（「已发布·有改动」），网站页面列表写「有改动还没发布」。原来那个通用的 `simple_form.html` 没人用了，删掉，换成 `draft_form.html`
7. **Markdown 编辑器**：原来每敲一个字发一次 `change`，自动保存会一个字存一次（`change` 对文本框是「离开了」，立刻存）。改成打字只发 `input`（停 0.8 秒存），离开编辑器时内容有变才发一次 `change`
8. 顺带：原来文章、网站页面保存时传了 `previous_revision`，Wagtail 把每次保存都记成「恢复了旧版本」（`wagtail.revert`）；改用 `save_draft` 后记成编辑
9. 设计 13.17、附录 D；`docs/admin.md` 4.2；README 文章、网站页面、改了就存三处

## 测试

`content/tests/test_drafts.py`（9 条）：

- 文章自动保存成草稿：网站上照旧是发布的那版，草稿里是新的
- 同一个人连续三次自动保存只多一份修订、一条编辑记录；隔了半小时、发布以后另起一份
- 别人接着改另起一份
- 新文章只写了正文就建好（标题、分类空着，回的 JSON 说了这两项、照样存）；列表写「（无标题）」「未选分类」；编辑页标题框是空的；没填好点发布被拦下；补上以后能发布
- 网址跟着标题走（回的 JSON 带新网址）；编辑自己改的不跟；发布以后不跟
- 一项有问题（标题清空）别的照存，标题保持原来的
- 网站页面、首页置顶、栏目介绍改了不上线，点发布才上线；网站页面列表只标一处「有改动」
- 编辑器的 `change` 只在离开时发（看源码）

改的旧测试：`backoffice/tests/test_backoffice.py` 里置顶和栏目介绍两条原来断言「保存就上线」，改成点「发布」。

## 命令输出

（所有检查都在测试机上跑；本机只改文件。）

第一次（新测试写完）：

```
FAILED content/tests/test_drafts.py::test_a_new_article_exists_from_its_first_change
FAILED content/tests/test_drafts.py::test_the_address_follows_the_title_until_published
```

第一条是真问题：新文章建好时写「创建」的操作记录，记录的名字取页面标题，标题是空的，Wagtail 的记录模型校验不过（`{'label': ['此字段不能为空。']}`），500。记录时把标题换成「（无标题）」。第二条是测试自己拿了一个旧的页面对象读最新修订（缓存着第一份），代码回的 `values` 已经对了；改成重新读。同一次还有 5 处行太长、3 个文件要重新排版：在测试机上跑 `ruff format`，把它改出来的差异拿回本机套上。

整组检查（改完全部以后）：

```
== ruff
All checks passed!
== pytest (11:20:59)
1884 条测试分成 4 片
分片 1：471 passed in 59.79s
分片 2：471 passed in 57.71s
分片 3：471 passed in 64.61s (0:01:04)
分片 4：471 passed in 54.62s
== 迁移 (11:22:09)
No changes detected
== 生产配置 (11:22:10)
System check identified no issues (0 silenced).
== Docker 镜像 (11:22:12)
构建成功：0fcd116c72ae
== 全部通过 (11:22:12)
```

变异（`mutate.py`，18 处）：

```
mutations: 18 not applying: none
baseline green, 10 tests
caught an autosave publishes -> test_an_article_saves_itself_as_a_draft
caught every save a new revision -> test_one_stretch_of_editing_is_one_revision
caught someone else's draft overwritten -> test_someone_else_starts_their_own_draft
caught the live revision overwritten -> test_one_stretch_of_editing_is_one_revision
caught an old draft overwritten -> test_one_stretch_of_editing_is_one_revision
caught each autosave logged -> test_one_stretch_of_editing_is_one_revision
caught a new article waits for its title -> test_a_new_article_exists_from_its_first_change
caught the address fixed on the first save -> test_the_address_follows_the_title_until_published
caught a typed address follows the title -> test_the_address_follows_the_title_until_published
caught a published address follows the title -> test_the_address_follows_the_title_until_published
caught the page not told the new address -> test_the_address_follows_the_title_until_published
caught a bad field saves nothing -> test_a_bad_field_keeps_its_value_and_the_rest_is_saved
caught a plain page published on save -> test_a_plain_page_waits_for_publish
caught the pins go live on save -> test_the_pins_and_the_intro_wait_for_publish
caught the intro goes live on save -> test_the_pins_and_the_intro_wait_for_publish
caught 「发布」 does not publish -> test_the_pins_and_the_intro_wait_for_publish
caught the editor saves per keystroke -> test_the_editor_saves_after_a_pause_not_per_keystroke
caught no form save without the script -> test_a_member_writes_saves_and_publishes
restored and green; missed: none
```

浏览器（测试机）：

```
== admin
ok  新文章打第一个字就建好（分类还空着） /admin/articles/9/|有 1 项没存（其余已保存 19:24）：分类：必需字段
ok  编辑器起来了，工具栏有图标 17
ok  工具栏图标画得出来
ok  对话框里选了封面 1
ok  刷新以后草稿还在（标题、封面、正文） 浏览器写的文章|1|true
ok  文章发布了
ok  封面留在文章上
ok  浏览器没有报错
全部走通
== journey
全部走通
== pages
看了 174 个地址，0 处有问题
全部走通
```

## 部署（正式站）

有迁移，先备份：

```
已备份到 /app/backups/sjtu-ow-20261005-193534.tar.gz（210.8 MB）
```

删了一个模板，先挪到 `/root/gone205/`：

```
moved backoffice/templates/backoffice/content/simple_form.html
```

`deploy_ship.sh 205`（18 个文件）：

```
 Image sjtu-ow-web Built 
 Image sjtu-ow-worker Built 
  Applying content.0011_article_category_while_draft... OK
 Container sjtu-ow-worker-1 Started 
全量生成完成：成功 12，失败 0，删除 0；目录占用 277 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

正式站真实数据上只读检查：

```
pages: {'/admin/articles/': 200, '/admin/articles/new/': 200, '/admin/pages/': 200, '/admin/pages/pins/': 200, '/admin/pages/intro/': 200, '/admin/pages/5/': 200, '/admin/pages/6/': 200, '/admin/pages/7/': 200, '/admin/articles/8/': 200}
autosave form: True hidden save button: True
category may be empty on a draft: True required to publish: True
articles: 1 live: 1
```

（等备份结束的循环又把自己的命令行当成还在跑的备份，手动停了；备份本身已经写完。）

## 没做 / 没验证

- 赛事、内战、分队编队、队长的战队管理、定时任务去重：206
- 用户问「你的测试为什么没有在测试机上而是在本地？」——这一轮的测试、变异、走查、格式化都在测试机上跑（日志在 `/srv/sjtu-ow-check/runs/`）；本机只跑了改文件的小脚本（`uv run python 临时目录/xxx.py`），看起来像在本地跑东西。之后改文件只用编辑工具
- 投稿者在前台的投稿页（如果还有）没有改成自动保存；后台写文章是成员写文章的入口
