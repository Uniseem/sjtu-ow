# 111 默认头像池（报告）

## 素材

用户要「英雄的动漫大头贴」。找过的地方：

- 官网英雄列表页：每个英雄一张 256×256 头像（透明背景），53 个英雄，110 之前已经下载在临时目录。是游戏美术风格的 3D 立绘头像，不是手绘动漫风
- 110 抓的官网新闻 1729 张图里按 alt 搜「icon / spray / 頭像 / 噴漆」：16 张，都是喷漆、玩家头像拼在一起的活动奖励图或国家队图标，不是一套英雄大头贴
- 网上搜「官方 Q 版、动漫风大头贴」：只有授权周边（卫衣、手办）的介绍和同人画师的作品；同人作品版权是画师的，不用
- 游戏里的玩家头像、喷漆只在客户端里；守望先锋 Wiki 要过 Cloudflare 的人机验证，没有去绕

所以本轮放官网这 53 张。图库在后台可以换：以后有授权的动漫风头像，传进「默认头像」、删掉旧的就行。

## 做了什么

1. **设计 v6.9**：细节文档新增 2.4「默认头像」，2.2、2.3 指过去，版本 v6.7 → v6.9；`design.md` 3.5 表的头像行、13.2.5 表的头像行、13.2.7 `c-avatar`、13.13.4 刷新表的「账号停用、恢复」一行、附录 D
2. **`core/avatars.py`**（新）：`DEFAULT_AVATAR_COLLECTION = "默认头像"`；`load_pool()`、`in_pool()` 复用 `core/covers.py` 的图库查找（那几个函数加了集合名参数，默认还是「默认封面」，子集合同样算）；`pick(person, pool)`：有自己的头像、账号停用（注销也是停用）、图库空着都返回 None，否则 `ID mod 张数`
3. **上下文处理器** `core.context_processors.avatar_pool`：每页一个惰性的图库
4. **模板标签** `{% default_avatar person "fill-WxH" as face %}`（`core/templatetags/ow.py`）：图库里有这个人的图就出缩略图（`alt=""`、`loading="lazy"`），没有就是空字符串
5. **模板**：`components/avatar.html` 没头像时先试图库（`md`、`lg` 用 176 像素，其余 88 像素），没有才写首字；成员名片的大图（`members/index.html`，400 像素）同样
6. **刷新**：`content/signals.py` 判断图片在不在图库时两个图库都看（`_in_default_pool`），图进出「默认头像」也触发全站生成；`accounts/signals.py` 的公开字段加 `is_active`，账号停用、恢复时重新生成显示这个人的页面
7. **`init_site`** 建「默认头像」集合（`content/services.py` 的 `ensure_default_avatar_collection()`）
8. **测试**：`accounts/tests/test_default_avatar.py`（12 条）
9. **README**：默认头像图库一条；`init_site` 那段补上三个图片集合
10. **本机和演示站**：导入 53 张官网英雄头像到「默认头像」，标题「默认头像 · 英雄名」，说明写来源和「版权归暴雪娱乐」

## 命令输出

变异（`mutate.py`，12 处）：

```
baseline green, 12 tests
caught everyone gets the first face -> test_each_person_keeps_their_own_face
caught the pool overrides people's own pictures -> test_their_own_picture_wins
caught closed accounts get a face -> test_closed_accounts_keep_the_initial
caught an empty pool breaks the page -> test_an_empty_pool_keeps_the_initial
caught faces come from the cover pool -> test_the_folders_under_the_pool_count_and_others_do_not
caught every face looks the pool up -> test_a_long_list_looks_at_the_pool_once
caught pool faces load at once -> test_someone_without_a_picture_gets_a_pool_face
caught big faces use the small thumbnail -> test_someone_without_a_picture_gets_a_pool_face
caught the member card skips the pool -> test_the_member_card_uses_the_pool_too
caught the member card skips the pool -> test_no_template_prints_the_initial_without_trying_the_pool
caught changes to the avatar pool are missed -> test_changes_to_the_pool_regenerate_the_site
caught closing an account leaves stale faces -> test_closing_or_reopening_an_account_regenerates_its_pages
caught init_site makes no avatar pool -> test_init_site_makes_the_pool
restored and green; missed: none
```

整组检查（开发服务器停着）。第一次 `ruff format --check` 报 `core/covers.py` 一处（`pool_root` 的返回语句加了参数后能写成一行），格式化后：

```
All checks passed!
276 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
```

```
1288 passed in 155.23s (0:02:35)
```

本机导入：

```
53 missing []
added 53 | pool now 53
```

本机的 40 个演示用户都有头像。临时把前 3 个人的头像清掉（记下原来的图片编号），用 `runserver` 截了成员展示页：三张名片显示安燃、艾什、巴蒂斯特的英雄头像，压在各自的底图上；截完把头像写回去（`User.objects.filter(avatar=None).count()` 是 0）。

演示站（镜像时间 `2026-10-03T08:50:44+02:00`，容器里有 `core/avatars.py`）：

```
已确保图片集合：默认封面
已确保图片集合：默认头像
added 53 | pool now 53
全量生成完成：成功 46，失败 0，删除 0；目录占用 1604 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"}, "disk": {"ok": true, "detail": "free space 72.5%"}, "worker_heartbeat": {"ok": true, "detail": "ok (22s ago)", "affects_status": true}, "task_backlog": {"ok": true, "detail": "ok", "affects_status": true}}}
```

## 没做 / 未验证

- **演示站上看不到默认头像**：40 个演示用户都有你选的动漫插画头像，没动。要看效果，可以让我拿掉一部分人的头像，或者注册一个新账号
- 头像是 256 像素，名片大图要 400 像素，Wagtail 不放大，浏览器拉伸后略软
- 按主位置给对应英雄的头像（坦克给坦克英雄）没做
- 手绘动漫风的大头贴没找到能用的来源（见上面「素材」）

## 补记（推送之后，用户要求）

用户：「拿掉一半演示用户的头像，我看看默认头像效果」。在演示站跑 `drop_half_avatars.py`：偶数编号的 20 个演示用户去掉头像（图片还在图片库里，每人原来的图片编号存在服务器 `/root/avatars_removed.json`，要恢复按它写回），然后全量生成：

```
removed 20 | with picture 20 | without 20
全量生成完成：成功 46，失败 0，删除 0；目录占用 1604 KB
```

成员展示页截图：名片和全部成员列表里一半是英雄头像、一半是原来的动漫插画。
