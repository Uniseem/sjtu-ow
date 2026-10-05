# 199 后台每页的权限并进 placed（报告）

## 做了什么

1. **核对**：一个子任务把 92 个后台地址的视图逐个和所在标签的 `allowed` 比了一遍，结论写在 `request.md`（大部分一样；比标签松的有选图对话框、「发送测试邮件」「测试对象存储」；比标签严的有集合、分类和成员分组的新建删除、文章的通知全体成员、Markdown 传图、各种对象权限；四处先 404 后 403）
2. **文档**（先改）：`docs/admin.md` 原则 4、2 章「进门」、4 章开头、6 章测试；设计 10.3 里 Wagtail 通知的说法；附录 D v7.3
3. **`backoffice/nav.py`**：`placed(大类, 标签, 小标签, *, allowed=None)` 在进门之后查这一页的权限——默认是标签的 `allowed`（`tab_for()` 找标签，写错的标签在放置时就报 `ValueError`），不够就 `PermissionDenied`，视图不被调用；包好的视图带着 `backoffice_gate`，测试拿它核对
4. **新后台视图里删掉和标签一样的判断**：设置、用户与权限、战队的 `_superuser`；网站页面、图片的 `_allowed`；评论的 `_moderator`；赛事、内战的 `_tournament_manager` / `_scrim_manager`；分类、成员分组的「能改」。留下比标签多的：分类、成员分组的新建和删除（`_may` / `_group_may` 只查 `add_` / `delete_`）、图片上传要有能加图的集合、文章和页面和图片各自的对象权限。图片集合三页改成 `placed("content", "images", allowed=access.is_superuser)`
5. v7.0 以前的页面（报名审核、巡查记录、头像、分队、编队、字体、静态页、活动数据、手册、赛事内战的动作）自己的装饰器没动，和标签同一个判断
6. **「195 留下的审核通知代码」**：没有这样的代码。`content/notifications.py` 从 127 起只有新文章通知；195 指错了文件。相关的只有 `templates/wagtailadmin/notifications/base.txt`（Wagtail 自己的通知套本站的信），留着；10.3 里的说法改成现在的情况

效果上的变化：

- 选图对话框：能进后台、但哪个集合都不能选图的人，以前打开是空的，现在 403（默认的各个角色都有图片权限，没人受影响）
- 「发送测试邮件」「测试对象存储」：只有超管（以前有 `core.change_sitesettings` 的人也能点，默认没有组有这个权限）
- 分类、成员分组的编辑页，分队页和分队文字：没权限的人不管编号存不存在都是 403

## 测试

新文件 `backoffice/tests/test_door.py`，6 条：

- 门口在视图之前拒绝（假视图一次都没被调用），`allowed=` 比标签严时按它
- 写错的标签在放置时报错
- **扫全部后台地址**（「通知全体成员」除外）：每个地址的门就是它所在标签的 `allowed`（或登记的更严的那个），投稿者、内容编辑、赛事管理员、内战管理员里标签不给的，请求一律在门口 403（加起来超过 150 次）
- 分类、成员分组编辑和分队两页，编号存在不存在都是 403
- 选图对话框：没有图片权限的人 403，投稿者 200
- 只有「能改」的人不能新建、删除分类和成员分组；内容编辑打不开集合页

## 命令输出

测试机整组检查：

```
1817 条测试分成 4 片
分片 1：455 passed in 54.60s
分片 2：454 passed in 55.18s
分片 3：454 passed in 52.80s
分片 4：454 passed in 56.75s

== 迁移 (07:04:52)
No changes detected

== 生产配置 (07:04:53)
System check identified no issues (0 silenced).

== 错误页和模板一致 (07:04:55)

== Docker 镜像 (07:04:56)
构建成功：7620b9fd7498

== 全部通过 (07:04:56)
```

变异（测试机，`mutate.py`，8 处、14 次检查）：

```
baseline green, 6 tests
caught the door does not ask the tab -> test_the_page_is_refused_before_its_view_runs
caught the door does not ask the tab -> test_every_back_office_page_keeps_out_whoever_its_tab_is_not_for
caught the door does not ask the tab -> test_no_page_tells_an_outsider_whether_an_id_exists
caught the door does not ask the tab -> test_the_picture_dialog_is_for_people_who_may_use_pictures
caught a stricter page as loose as its tab -> test_the_page_is_refused_before_its_view_runs
caught a stricter page as loose as its tab -> test_every_back_office_page_keeps_out_whoever_its_tab_is_not_for
caught a stricter page as loose as its tab -> test_new_and_delete_still_need_their_own_permission
caught a wrong tab placed quietly -> test_a_tab_that_does_not_exist_is_caught_when_the_page_is_placed
caught collections for everyone with pictures -> test_every_back_office_page_keeps_out_whoever_its_tab_is_not_for
caught collections for everyone with pictures -> test_new_and_delete_still_need_their_own_permission
caught a new category with change only -> test_new_and_delete_still_need_their_own_permission
caught a category deleted with change only -> test_new_and_delete_still_need_their_own_permission
caught a new member group with change only -> test_new_and_delete_still_need_their_own_permission
caught a member group deleted with change only -> test_new_and_delete_still_need_their_own_permission
restored and green; missed: none
```

浏览器（测试机）：

```
看了 163 个地址，0 处有问题
全部走通
```

```
ok  卡片按钮移到缓冲区再移回 4/5
ok  保存分队
ok  三个散人移进新队伍 3
ok  保存编队
ok  新队伍出现在页面上
ok  编辑器起来了，工具栏有图标 17
ok  工具栏图标画得出来
ok  对话框里选了封面 1
ok  文章发布了
ok  封面留在文章上
ok  浏览器没有报错
全部走通
```

## 部署（正式站）

没有迁移，没有删文件。`deploy_ship.sh 199`（10 个文件）：

```
 Image sjtu-ow-web Built 
 Image sjtu-ow-worker Built 
 Container sjtu-ow-worker-1 Started 
全量生成完成：成功 12，失败 0，删除 0；目录占用 276 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

```
sjtu-ow-web 38 seconds ago
sjtu-ow-worker 38 seconds ago
```

正式站真实数据上只读检查（`/root/smoke199.py`，请求工厂调视图，24 个后台地址）：

```
superuser: all 200
no plain member to try
```

正式站上还没有普通成员，「被拒」这一半没有人可试（测试里覆盖了）。

## 没做 / 没验证

- 网站页面的预览不看对象权限、首页置顶和栏目介绍不看页面权限（内容编辑本来都有）：没动
- 评论的未知动作 403、赛事内战的 404：没统一
- v7.0 以前那些页面自己的装饰器留着（和门口同一个判断，多一道）
