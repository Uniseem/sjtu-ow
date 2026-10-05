# 209 用户协议、隐私政策定稿；首页大字改回两行中文（报告）

## 做了什么

用户 10-05：「用户协议什么的开始和我商讨完善吧」，中途：「然后还有就是，首页的大字改回中文的两行」，最后：「我觉得没什么问题啊，先推送吧，正式站也上去」（设计 v7.13）。

1. **商量前先核实**（正式站只读）：社区成立日期、QQ 群链接已填；发信是网易 126；AI 审核没开（没填密钥）；异地备份没开，站点的 `backup` 每天北京时间 3 点跑、保留 14 天，本地那份不加密；网站自己的 Caddy 不记访问日志。隐私政策原文「每天加密备份到 Cloudflare 对象存储」和实际不符
2. **两轮问答**（用户的答复见 `request.md`）：运营方「SJTU-OW 管理组」，联系方式邮箱 ow4sjtu@126.com + QQ 群，未满 14 周岁不要注册，生效日期定稿那天；服务器 Contabo 法国、ZgoCloud 德国反代（不记日志，只转发）、两者之间走 Cloudflare WARP；备份照实写（每天一次、保留 14 天）；AI 审核照写 DeepSeek；关于我们用户自己写
3. **改 `content/legal/terms.md`、`privacy.md`**（仓库里的定稿，新建站点也用它）：
   - 用户协议：站名 SJTU-OW、运营方、未满 14 周岁不要注册（账号一节第 6 条）、通知渠道、联系方式、生效日期
   - 隐私政策：站名、运营方、发信服务商「网易 126 邮箱」、新加「服务器和网络」一条（Contabo、ZgoCloud、Cloudflare WARP）、存储地点写明法国的服务器保存、德国的服务器只转发、经 Cloudflare 加密网络传输、两者都不保存不记日志；删掉不实的「加密备份到 Cloudflare」，保存期限改成「备份：每天一次，保留最近 14 天」；未成年人；联系方式（个人信息的请求用邮件）
   - 两份都没有【】了；文件头的说明改成定稿
4. **首页首屏大字改回两行「上海交通大学」「守望先锋社区」**（第二行橙色），站名别处照 v7.12 写 SJTU-OW；设计 13.2「站点名称」写明这一处例外
5. 发布：正式站先备份、部署，再 `load_legal_pages --force`（旧版留在 Wagtail 修订历史里）

## 测试

- `content/tests/test_legal_pages.py`：隐私政策要点名实际在用的处理方（DeepSeek、网易 126 邮箱、Contabo、ZgoCloud、Cloudflare，原来查的是 Cloudflare 和「发信服务商」这个占位词），并且不留【】
- `core/tests/test_setup_checklist.py`：上线清单那条原来靠草稿里的【】，现在自己放一段带【】的正文
- `core/tests/test_site_name.py`：首页大字断言改成两行中文

## 命令输出

（所有检查都在测试机上跑；本机只改文件。）

第一次整组停在格式检查（新测试里一个字符串用了单引号），pytest 没跑到。改了重跑，红一条：

```
FAILED content/tests/test_legal_pages.py::test_the_command_publishes_both_drafts
E           AssertionError: assert '**' not in '\n<!DOCTYPE...>\n</html>\n'
```

隐私政策里「**未满 14 周岁的未成年人请不要注册本站账号。**如果」：句号在加粗里面、后面紧跟文字，Markdown 的规则不把它当加粗结束，星号原样显示。把句号挪到外面。再跑：

```
== ruff (15:40:36)
All checks passed!
403 files already formatted
== pytest (15:40:38)
1904 条测试分成 4 片
分片 1：476 passed in 56.38s
分片 2：476 passed in 66.12s (0:01:06)
分片 3：476 passed in 62.78s (0:01:02)
分片 4：476 passed in 58.54s
== 迁移 (15:41:49)
No changes detected
== Docker 镜像 (15:41:53)
构建成功：c013b4509f13
== 全部通过 (15:41:53)
```

变异（`mutate.py`，4 处）。第一次漏了一处：

```
restored and green; missed: [('the forwarding server left out', 'content/tests/test_legal_pages.py::test_the_privacy_draft_names_every_processor_the_site_uses')]
```

变异写得不对：隐私政策里 ZgoCloud 出现两次，只去掉一处照样点了名。改成全文都去掉（脚本改成每处都换），重跑：

```
mutations: 4 not applying: none
baseline green, 3 tests
caught the forwarding server left out -> test_the_privacy_draft_names_every_processor_the_site_uses
caught a blank left in the policy -> test_the_privacy_draft_names_every_processor_the_site_uses
caught the hero back on one line -> test_the_pages_letters_and_settings_say_sjtu_ow
caught blanks not counted -> test_the_agreements_need_their_blanks_filled
restored and green; missed: none
```

浏览器：新人那一晚「全部走通」（格式错的那次跑的，代码和这次只差测试里的引号和隐私政策里的一个句号）；`journey.py pages` 跑到一半，用户问为什么测试机 CPU 低（那一步一页一页开、每页等 1.5 秒），之后用户说先上线，手动停了，**这一次没跑完**。

## 部署（正式站）

```
已备份到 /app/backups/sjtu-ow-20261005-234258.tar.gz（210.8 MB）
```

`deploy_ship.sh 209`（7 个文件）：

```
 Image sjtu-ow-web Built 
 Image sjtu-ow-worker Built 
 Container sjtu-ow-worker-1 Started 
全量生成完成：成功 12，失败 0，删除 0；目录占用 276 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

发布两页：

```
已发布「用户协议」
已发布「隐私政策」
```

正式站上（只读；后三行是从服务器本机经 Caddy 取的页面，就是访客拿到的）：

```
terms live: True blanks: 0
privacy live: True blanks: 0
checklist: 用户协议 done: True | 已填写。
checklist: 隐私政策 done: True | 已填写。
/: c-hero__title"><span>上海交通大学</span><span>守望先锋社区</span>  【=0 **=0
/terms/:  生效日期：2026 年 10 月 5 日 【=0 **=0 SJTU-OW 管理组
/privacy/:  生效日期：2026 年 10 月 5 日 【=0 **=0 SJTU-OW 管理组 ZgoCloud
```

## 没做 / 没验证

- 关于我们：用户自己写
- 隐私政策写「ZgoCloud 的转发服务器和 Cloudflare 不保存、不记录访问日志」是用户确认的，我没法核实那两边的设置
- AI 审核写了 DeepSeek，但现在还没开；用户说马上填密钥
- 这不是法律意见；条文按网站实际的数据处理写，必要时请学校相关部门把关
