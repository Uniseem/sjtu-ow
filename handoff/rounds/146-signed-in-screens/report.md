# 146 测试机上截登录后的页面（报告）

## 做了什么

1. 测试机：`apt-get install chromium fonts-noto-cjk`（Chromium 154）
2. `scripts/screens.py`：
   - `seed()`：在 Django 里建三个人（成员、队长、队友，带游戏 ID、联系方式）、一支战队（填了队内联系方式）、个人赛（成员在散人池里，填了选手联系方式）、整队赛（队长提交了报名）、内战（成员报了名），用 `Client.force_login` 给成员和队长生成会话
   - `shoot(width)`：`/tmp/sjtu-ow-screens` 下新建数据库和上传目录，迁移、`init_site`、填数据；开发服务器和 Chromium 各用一个空闲端口；每个页面先设 `sessionid` Cookie 再打开，截整页
   - 等开发服务器起来用 `/robots.txt`：第一次用 `/healthz`，没有 worker 心跳时它返回 503，一直等不到
3. AGENTS.md：常用命令里写用法，测试机一节记装了什么

## 跑的结果

```
/tmp/sjtu-ow-screens/out/me-profile-375.png  2745px
/tmp/sjtu-ow-screens/out/me-registrations-375.png  1882px
/tmp/sjtu-ow-screens/out/me-teams-375.png  1633px
/tmp/sjtu-ow-screens/out/me-scrims-375.png  1396px
/tmp/sjtu-ow-screens/out/team-as-member-375.png  2602px
/tmp/sjtu-ow-screens/out/team-manage-375.png  3490px
/tmp/sjtu-ow-screens/out/cup-in-pool-375.png  2154px
/tmp/sjtu-ow-screens/out/teamcup-as-captain-375.png  1874px
/tmp/sjtu-ow-screens/out/scrim-signed-up-375.png  2081px
/tmp/sjtu-ow-screens/out/teams-by-role-375.png  1740px
```

看过的：「我的报名」两张卡片都有比赛时间；个人赛页报名区「已个人报名，等待编队」下面一行「选手联系方式：选手群 987654321」；战队主页「你已是成员 / 退出战队」下面一行队内联系方式；队长管理页的「队内联系方式」输入框和说明；内战页报名区（测试数据没填 QQ 群链接，所以没有群链接那一行，符合 138 的规则）。手机宽度下都没有挤压、溢出。唯一不对劲的是文件选择框写「Choose File / No file chosen」，那是无头浏览器的界面语言，中文浏览器里是「选择文件」，不是网站的问题。

整组检查（测试机）：

```
== 生产配置 (22:22:25)
System check identified no issues (0 silenced).
== 错误页和模板一致 (22:22:26)
== Docker 镜像 (22:22:27)
构建成功：cf7d8435a565
== 全部通过 (22:22:27)
```

## 没做 / 未验证

- 深色模式、桌面宽度没截（脚本支持换宽度，深色要在 `Emulation.setEmulatedMedia` 里加）
- 后台页面没截
