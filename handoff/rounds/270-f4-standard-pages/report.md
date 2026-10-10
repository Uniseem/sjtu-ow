# 270 实现报告

## 结论

**部分完成**。前端这一侧做完了：普通页（关于、协议、隐私和其他 `/<slug>/`）、搜索、投稿三组页面照旧模板重写，SSR 测试和 12 处变异都过了。对拍 6 行里 1 行通过（访客的投稿页）；其余几行差在 Go，前端不能单独修完，写进了 STATUS「交给后端（GPT）」：

- 三个普通页在新站是 404，是 **Go 导入程序的 bug**（BE-0）：它读旧库里不存在的表 `content_sitepage`（旧站叫 `content_standardpage`），报错被吞掉，普通页一条都没导进新库。割接前必须修
- 搜索差 BE-2（Go 的回答没有分组和摘录）
- 成员的投稿页两边都 302 去写文章，差在目的地（新后台写文章页还是 260 的，F9）

## 逐条结果

1. **普通页** `pages/StandardPage.vue`：照 `standard_page.html`，三页切换标签（当前页 `aria-current="page"`）、标题、「最后更新」（上海时区，`Y.m.d`，没有日期就不显示这一行）、正文。标题用 `seo_title`，没有就用页面标题（`SeoPageMixin.get_share_title`），描述用 `search_description`。`/about/`、`/terms/`、`/privacy/` 和新的 `/:slug(...)/` 都指向它。slug 的写法照 Wagtail：字母数字、下划线、横线、非 ASCII（所以百分号编码的字节也算），**不含点**：`/wp-login.php/`、`/.env/` 这类扫描地址直接 404、不问 Go；多段地址同样不匹配。固定路由的优先级高于它（测试逐个查了 `/news/`、`/teams/`、`/admin/` 等）
2. **搜索** `pages/Search.vue`：照 `results.html`。查询去空白截 50 字、最多 5 个词，**没有词就不调 Go**（不算进限流，和旧站一样）；说明文字、没结果的空状态、「「q」共 N 条结果」、四组按顺序、`search-N` 按组的位置编号（空组不显示但占号，和旧站的 `forloop.counter` 一致）、摘录、标签、「只显示前 20 条」；Go 的 429 是 429 页。标题「搜索：q · 站内搜索 · SJTU-OW」，描述照旧
3. **投稿** `pages/Submit.vue`：照 `submit_entry`。访客：「未登录」+「去登录」（`next=%2Fsubmit%2F`）；投稿者（超管或 `caps` 有 `articles.publish_own`）302 去 `/admin/articles/new/`；验证过邮箱但不是投稿者：「没有投稿权限」+「返回个人中心」；没验证邮箱：「邮箱未验证」，会话里有 `can_submit_article: false` 时再加「没有投稿权限」（BE-3）
4. **后端缺口的写法**：`web/apps/site/src/pending-api.ts` 写页面期望的形状，每段带 `[BE-n]`；`STATUS.md` 新加「交给后端（GPT）」一节写规格。后端做完一条就删对应的一段、改用生成的类型。搜索的类型转换只在 `searchSite()` 一处
5. **底座**：`meta.ts` 的 `usePageMeta()` 统一出 `<title>`（`页面 · SJTU-OW`，站名本身不重复）和描述；canonical、og、站点默认描述要 Go 给站点设置，没做（写进下面）。加载器上下文加 `viewer()`：返回 SSR 已经在取的同一个 `/api/session`（测试断言只调一次），客户端换页时是当前的会话
6. **`v-html` 白名单**：删掉 GPT 草稿里的通用 `components/ServerHtml.vue`（任何页面都能把任意字符串交给它），白名单改成 `pages/StandardPage.vue` 本身，注释写明「每个显示 `body_html` 的页面自己列进来，不要通用组件」
7. **占位路由**：`routes.ts` 里只有标题的 `page(...)` 从 23 条减到 18 条，守卫的上限从 34 收紧到 18（只降不升）

## 验收输出

全部在测试机后台跑（`scripts/remote-check.sh`），本机没编译、没测试。

| 日志 | 内容 | 结果 |
|---|---|---|
| `20261010-215404-f561cc3` | `content`、`guards`、`routes` 三个测试文件 | 20 条通过，退出 0 |
| `20261010-215650-0c0b794` | 加上搜索、投稿后的五个测试文件 | 41 条通过，退出 0 |
| `20261010-215811-1f94fca` | 整组 → browser-check → 变异 → 对拍，用 `;` 串起来 | 整组**红 2 条**（见下）；browser-check 打印 OK 但这次整组没走到构建，用的是旧产物，**不算数**；变异 `MUTATIONS-OK 12`；对拍 `PARITY 1/6`，退出 0（没加 `--strict`） |
| `20261010-220211-0cc95f3` | 修了上面两条后重跑整组 | **红 1 条**：我用 `sed` 改测试里的地址时把另一条测试（样张邮件只给工作人员）的地址也改了，改回 |
| `20261010-220305-6937df1` | 整组 + browser-check | 整组**全绿**（Web 15 + 171 条）；browser-check **4 项没过**：它也拿一段的 `/no-such-page/` 测 404，而它的桩接口对任何地址都回 200 |
| `20261010-220454-f798313` | browser-check 的桩接口改成像 Go 一样对没有的普通页回 404 后，整组 + browser-check | **全部通过**：Go 五项（govulncheck 无漏洞）、Web 15 + 171 条、首页壳 gzip 95016 字节 BUDGET-OK、BROWSER-CHECK-OK，退出 0 |

第一次整组红的两条是 `handle.test.ts` 拿 `/no-such/` 当「没有这个路由」：现在一段的地址是普通页，会先问 Go。改成两段的 `/no/such/`（仍然测「没有路由 → 404、无脚本」），一段地址问 Go 后 404 的情况由 `content.test.ts` 管。另一条「组件渲染时抛错是 500」原来借 `/about/` 的占位页，改借 `/unsubscribe/tok/`（还是只有标题的 `Page.vue`，注释说的「Page.vue 在 setup 里读标题」才成立）。

变异（`mutate.py`，每处原文先核对只出现一次）12 处全部被抓到：

```
CAUGHT current about tab
CAUGHT SEO title wins
CAUGHT no update line without a date
CAUGHT slug never has a dot
CAUGHT document title format
CAUGHT empty query does not call Go
CAUGHT query cut to 50
CAUGHT group ids count every group
CAUGHT 20-hit note only when cut
CAUGHT contributor goes to the editor
CAUGHT unverified is not also called banned
CAUGHT load shares the page's session call
MUTATIONS-OK 12; restored baseline green
```

对拍（`e2e/parity/run.sh --only=about,terms,privacy,search,submit --wide`，报告原文 `parity-report.md`）：

| 地址 | 身份 | 结论 | 原因 |
|---|---|---|---|
| `/about/`、`/terms/`、`/privacy/` | 访客 | 不同（200 / 404） | BE-0：普通页没导进新库。导进来以后还差「最后更新」（BE-1） |
| `/search/?q=截图` | 访客 | 不同 | BE-2：Go 回的是五个平列表，没有 `groups`，页面显示「没有找到」 |
| `/submit/` | 访客 | **通过** | 四种组合（375/1280 × 浅/深） |
| `/submit/` | 成员 | 不同（302 / 302） | 两边都跳去写文章；差的是目的地的后台写文章页（260 的，F9 重写） |

## 设计偏差

无。页面照旧模板，没改设计。

## 未完成 / 顺带发现 / 需要确认

- **BE-0 是割接的硬阻碍**：同一个文件里别的段也是 `if err == nil { … }` 加 `_, _ =`，导入出错不报。写进 BE-0，请后端一起改成报错
- `usePageMeta` 还缺 canonical、`og:*`、站点默认描述和默认分享图：要 Go 给站点设置（`site_description`、`default_share_image`、站点地址）。没编号，等做 A11 那一轮一起提
- 搜索结果的「加载」不走客户端换页：表单是普通的 GET 提交（和旧站一样，没脚本也能用），每次搜索整页加载
- 普通页标签栏在任何普通页上都显示（旧模板也是这样，不是新问题）
- 种子数据里没有「没验证邮箱又被禁投稿」的人，BE-3 那一种情况只有 SSR 测试，没有对拍

## 改动文件

- 新：`web/apps/site/src/pages/StandardPage.vue`（接手重写）、`pages/Search.vue`、`pages/Submit.vue`、`meta.ts`、`pending-api.ts`、`content.test.ts`
- 删：`web/apps/site/src/components/ServerHtml.vue`（GPT 的草稿，没提交过）
- 改：`routes.ts`、`router.ts`、`entry-server.ts`、`entry-client.ts`、`guards.test.ts`、`handle.test.ts`、`browser-check.mjs`（桩接口对没有的普通页回 404）；`AGENTS.md`（前后端分工）
- 文档：本轮 `request.md`、`report.md`、`review.md`、`mutate.py`、`parity-report.md`；`handoff/STATUS.md`
