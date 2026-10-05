# 208 站点名称改成 SJTU-OW（报告）

## 做了什么

用户 10-05：「哦对，站点名称使用 SJTU-OW」，问过范围后选「全站的名称都换」（设计 v7.12，13.2「站点名称」）。

1. **当名字用的地方都写 SJTU-OW**：
   - 页头页脚的站名（`components/brand.html`）、每页标题后缀「· SJTU-OW」（26 个模板）、首页首屏大标题（一行「SJTU-OW」，「OW」橙色；原来两行中文）、旧的首页模板、页脚 ©
   - 手机桌面图标名（`manifest.webmanifest` 的 name、short_name）、分享卡片：`content/seo.py` 的站点名，并补上一直没输出的 `og:site_name`
   - Wagtail 站点名（`WAGTAIL_SITE_NAME`、`SITE_DISPLAY_NAME`）、Wagtail 底层后台的名字和标签页
   - 错误页、维护页（改了模板，在测试机上 `render_error_pages` 重新生成 `deploy/error_pages/maintenance.html`，拿回本机提交）
   - 邮件：页头站名、落款、账号邮件（验证码、找回密码、已注册、没注册）正文里的站名、Wagtail 通知邮件落款、发件人默认名「SJTU-OW」、主题前缀默认 `[SJTU-OW]`
   - 日历订阅的标识、字体预览示例文字（以 SJTU-OW 开头）
   - 顺带：三个赛事报名页的标题原来没有站名后缀（个人报名、为战队报名、报名详情），新测试查出来，补上
2. **说明它是什么的句子留着**：首屏简介、页脚说明改成「SJTU-OW 是上海交通大学守望先锋玩家的社团网站，由学生社团自己建设和维护。不是上海交通大学官方网站……」、页面描述默认值「SJTU-OW：上海交通大学守望先锋玩家的社团网站」、邮件页头站名下面的小字「上海交通大学守望先锋玩家社区」、AI 审核提示词说网站是什么
3. **数据库里的**（迁移 `core/0024`）：全站设置的发件人名称、主题前缀、Wagtail 站点名还是原来默认值的改成新的，站长自己改过的不动；两个字段的默认值跟着改
4. 不改：用户协议、隐私政策、关于我们的页面内容（数据库里，站长在后台改）；样张页里示例赛事「2026 秋季交大守望先锋杯」
5. 设计 13.2（站点标志、站点名称）、13.13 首屏、10.3 页头和落款、附录 B/C 默认值、附录 D；README、AGENTS.md 开头

## 测试

`core/tests/test_site_name.py`（4 条）：

- 模板、Python、manifest、脚本里没有旧名字（「上海交通大学守望先锋社区」「交大守望先锋」「SJTU OW」「SJTU 守望先锋社区」），只放过样张页那个示例赛事；迁移、测试、文档、生成的目录不扫
- 前台模板里带「·」的标题都以「· SJTU-OW」结尾
- 首页：页头站名、标题、`og:site_name`、首屏大标题、页脚说明；信的落款和页头；发件人、主题前缀、Wagtail 站点名
- 迁移：还是旧默认值的发件人名改了，站长自己的前缀没动

改的旧测试：断言旧名字的 8 处（页面标题、底层后台标签页、主题前缀默认值三处、信的落款、信的页头、首页、桌面图标名）。

## 命令输出

（所有检查都在测试机上跑；本机只改文件。错误页在测试机上生成。）

第一次整组：断言旧名字的旧测试红了一片（预期的），新测试红两条：

```
E   AssertionError: ['个人报名 · {{ tournament.title }}', '报名详情 · {{ registration.tournament.title }}', '为战队报名 · {{ tournament.title }}']
E   assert 'property="og:site_name" content="SJTU-OW"' in '...'
```

第一条：三个报名页的标题本来就没有站名后缀，补上。第二条：`content/seo.py` 里一直有站点名，但模板从没输出 `og:site_name`，补上这一行。

整组检查（最后一次）：

```
== ruff
All checks passed!
== pytest
1904 条测试分成 4 片
分片 1：476 passed in 52.41s
分片 2：476 passed in 65.37s (0:01:05)
分片 3：476 passed in 57.59s
分片 4：476 passed in 53.22s
== 迁移
No changes detected
== 生产配置 (14:46:35)
System check identified no issues (0 silenced).
== 错误页和模板一致 (14:46:36)
== Docker 镜像 (14:46:37)
构建成功：755ea6412f78
== 全部通过 (14:46:38)
```

变异（`mutate.py`，9 处）：

```
mutations: 9 not applying: none
baseline green, 5 tests
caught the old short name in the header -> test_no_old_name_is_left
caught the old short name in the header -> test_the_pages_letters_and_settings_say_sjtu_ow
caught a page title with the old suffix -> test_no_old_name_is_left
caught a page title with the old suffix -> test_every_page_title_ends_with_the_name
caught a page title without the name -> test_every_page_title_ends_with_the_name
caught the old signature on letters -> test_no_old_name_is_left
caught the old signature on letters -> test_the_pages_letters_and_settings_say_sjtu_ow
caught the old signature on letters -> core/tests/test_letters.py
caught the old prefix by default -> test_no_old_name_is_left
caught no share-card site name -> test_the_pages_letters_and_settings_say_sjtu_ow
caught the hero keeps the old two lines -> test_the_pages_letters_and_settings_say_sjtu_ow
caught stored defaults stay old -> test_stored_old_defaults_follow_and_changed_ones_stay
caught the owner's own prefix overwritten -> test_stored_old_defaults_follow_and_changed_ones_stay
restored and green; missed: none
```

浏览器（测试机）：干部那一晚、新人那一晚「全部走通」；`journey.py pages`「看了 174 个地址，0 处有问题」。首页截图（375 和 1280 宽）看过：页头「SJTU-OW」，首屏一行「SJTU-OW」、「OW」橙色，页脚说明和 ©。

## 部署（正式站）

有迁移，先备份：

```
已备份到 /app/backups/sjtu-ow-20261005-230315.tar.gz（210.8 MB）
```

`deploy_ship.sh 208`（74 个文件）：

```
 Image sjtu-ow-web Built 
 Image sjtu-ow-worker Built 
  Applying core.0024_site_name_sjtu_ow... OK
 Container sjtu-ow-worker-1 Started 
全量生成完成：成功 12，失败 0，删除 0；目录占用 276 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

正式站上（只读）：

```
from_name: SJTU-OW
subject prefix: [SJTU-OW]
from header: SJTU-OW <ow4sjtu@126.com>
wagtail site: SJTU-OW
<title>首页 · SJTU-OW</title>
og:site_name" content="SJTU-OW"
c-brand__name">SJTU-OW<
c-hero__title"><span>SJTU-</span><span>OW</span>
```

（最后几行是从服务器本机经 Caddy 取的首页，也就是访客拿到的预渲染静态页。）

## 没做 / 没验证

- 用户协议、隐私政策、关于我们的正文在数据库里，里面写的名称（和【】待填的运营方）没动，要改在后台「网站页面」改
- 全站设置的「站点简介」（站长填的）没动
- 正式站上没有再发一封信看新的发件人和前缀长什么样（上面读出来的设置已经是新的）
