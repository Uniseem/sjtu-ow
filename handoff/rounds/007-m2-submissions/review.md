# 007 复核结果

## 结论

**通过。** 两处修正到位，投稿的权限边界我自己逐条验证过，没有发现问题。

## 验证记录

| 项目 | 我的验证方式 | 结果 |
|---|---|---|
| ruff / pytest / 迁移 / `check --deploy` | 本地重跑 | 通过，**122 个测试** |
| **T1 站点主机名** | 自己用 `SITE_URL=https://ow.sjtu.example.cn` 跑 `init_site` | 站点记录变成 `ow.sjtu.example.cn:443`，文章绝对地址变成 `https://ow.sjtu.example.cn/news/…`；跑回原值后恢复 ✅ |
| **T2 B 站解析** | 直接调 embed finder | 长链、移动端链接都 accept；YouTube 和无关域名被拒；解析出 `player.bilibili.com/player.html?bvid=…` ✅ |
| T2 CSP | 读 settings | `frame-src` 只有 `'self'` 和 `https://player.bilibili.com`，YouTube / Vimeo 已去掉 ✅ |
| T2 前台渲染 | 抓文章页 HTML | iframe 地址正确，**没有内联 style** ✅ |
| **T3 组同步** | 自己建用户走一遍 | 验证邮箱后自动进「投稿者」；加一条禁用规则后自动移出；删掉规则后又回来 ✅ |
| T3 `/submit/` | 两种身份访问 | 投稿者 302 到后台新建稿件页；未登录 200 并说明原因 ✅ |
| **投稿者后台边界** | 用投稿者身份登录后自己点 | 后台首页没有赛事、内战、报名审核、用户、功能权限、全站设置、页面树；有「我的投稿」和「新建投稿」 ✅ |
| 直达受限网址 | 逐个请求 | `/admin/users/`、`/admin/settings/core/sitesettings/`、`/admin/snippets/…` 全部被弹回 `/admin/`；`/admin/pages/` 落到已过滤的栏目列表 ✅ |
| **能否看到别人的稿件** | 造一篇别人的未发布稿 | 侧边栏 API 只返回已发布页 + 自己的稿件，**看不到别人的未发布稿**；直接打开别人的编辑页被弹回（302），打开自己的是 200 ✅ |
| **能否自己发布** | 查页面权限 | 自己的稿件：可编辑、**不可发布**；别人的稿件：都不可 ✅ |
| 编辑页字段 | 抓编辑页 HTML | 没有「作者」字段；分类下拉里没有「公告」「赛事通知」 ✅ |
| 前台回归 | 逐个请求 | `/`、`/news/`、`/robots.txt`、`/sitemap.xml`、`/submit/` 全部 200 ✅ |
| Docker / git | `docker images` / `git status` | 镜像 16 分钟前重建、ID 与报告一致 ✅ |

未独立验证的两项（采信报告 + 现有测试）：`b23.tv` 短链需要真实网络跳转，它的测试用的是 mock；工作流的提交与审核邮件，我验证了权限边界（投稿者不能发布），邮件正文以报告为准。

## 必须修

无。

## 建议（下一轮顺带）

工作区里 `docs/design.md` 的 v1.5.4 改动（我在 006 复核时写的）还没提交，008 提交时一并带上。

## 认可的判断

- 发现 `construct_explorer_page_queryset` 只作用于搜索，真正的列表和侧边栏走 `PagePermissionPolicy.explorable_instances`，于是对后者做了同样的过滤——这正是设计 14.3 节里我标注「需要实测」的那一条，它实测并解决了
- `construct_main_menu` 用 `order=1000` 避免被后写入的菜单项冲掉，是踩过坑才会写的顺序
- Wagtail 对无权限的后台网址是弹回控制面板而不是 403，测试按重定向链和页面正文断言，判断正确
- 「投稿者-only」的判定排除了内容编辑等角色，避免内容编辑被误降级成精简菜单

## 文档更新

本轮无需改设计文档。
