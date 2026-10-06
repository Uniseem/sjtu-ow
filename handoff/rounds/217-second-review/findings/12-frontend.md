# 217 复核 · 12 前端脚本与模板

复核对象：`static/js/` 全部 12 个文件（autosave、backoffice、state、scrim-split、tournament-teams、markdown-editor、theme、app、arrival、loading、contextmenu、typography-preview）、`static/vendor/` 与 `THIRD_PARTY_NOTICES.md`、模板的 XSS / CSP / 表单无障碍。基线 `e417b2e`。

**复现情况**：浏览器探针 `findings/12-probe.py`（复用 `scripts/screens.py` 的种子数据，在无头 Chromium 里跑 12-1、12-2、12-5，并量 375 宽的横向溢出）。交回结果以后测试机才跑完（run `20261007-033833-6f4cfda`，退出码 0），输出已补进下面各条。12-2、12-5 已复现；12-1 的症状复现了，但对照组也是 403，原因还没弄清（见该条）。修的那一轮可以再跑一次：

```
bash scripts/remote-check.sh run uv run python handoff/rounds/217-second-review/findings/12-probe.py
```

## 中

### 12-1 在别处重新登录以后，本页的自动保存一直 403；永久失败以后离开页面也不再提醒，改动静静丢掉

- **严重度**：中
- **位置**：`static/js/autosave.js:29-36`（`token()` 先读表单里的 `csrfmiddlewaretoken`，Cookie 只是兜底）、`:154-160`（`pending()` 在 `gaveUp` 时返回 false）、`:217-241`（401/403/404 和「200 但不是 JSON」都算永久失败）；同样的取令牌方式在 `static/js/backoffice.js:45-48`、`static/js/markdown-editor.js:17-23`。对照：`static/js/app.js:96-100` 给 htmx 用的是 Cookie 里的令牌
- **问题**（原因的推断见「状态」：对照组同样 403，这里的推断还没证实）：Django 的 `login()` 会调 `rotate_token`，换掉 Cookie 里的 CSRF 密钥。页面上表单里的令牌还是旧密钥算出来的，所以只要在别的标签页重新登录过，这一页之后每次自动保存都是 CSRF 403，状态栏写「保存失败：登录状态已失效或没有权限，重新登录后再改」。可用户已经重新登录了，照提示做也恢复不了，只能刷新。而永久失败的时候 `gaveUp = true`，`pending()` 返回 false，`beforeunload` 不再拦，刷新或关标签页时没有任何提醒，会话失效以后打的字全部丢掉。设计 13.17 写的是「离开页面时还有没存完的，浏览器提醒」，也写了「重新登录后再改」，这两条现在都做不到
- **失败场景**：编辑在后台写一篇长文章，中途会话失效（另一个标签页退出又登录、在别处改了密码、会话到期）。状态栏提示重新登录，他在新标签页登录后回来接着写，状态栏还是同一句失败提示；他按刷新，浏览器不拦，失效以后写的全部丢掉。Markdown 编辑器的预览和插图上传也是一样 403（上传还会提示「检查网络」）
- **怎么验证**：探针 A 段：用成员会话打开 `/me/`，改昵称，基线状态是「已保存」；然后把浏览器的 `sessionid` 换成同一用户的新会话、`csrftoken` 换成新随机值（等同于重新登录），再改昵称，读状态栏、派发一个可取消的 `beforeunload` 看 `defaultPrevented`，查库里的昵称。对照组：同一张表单改用 Cookie 里的令牌 `fetch`，应该是 200 JSON 并且存上
- **状态**：**症状已复现，原因没有确认**。探针 A 段的真实输出：
  ```
  基线（没换 Cookie）：状态栏 = 已保存 03:44
  基线：库里的昵称 = 截图队员A
  换成新会话和新 CSRF Cookie 以后：状态栏 = 保存失败：登录状态已失效或没有权限，重新登录后再改
  再改一次：状态栏 = 保存失败：登录状态已失效或没有权限，重新登录后再改
  这时离开页面会不会被拦（beforeunload 被 preventDefault）= False
  库里的昵称 = 截图队员A
  对照：同一张表单、用 Cookie 里的令牌发 = 403 text/html; charset=utf-8
  ```
  重新登录以后一直存不上、离开不拦、库里没变，这三点都复现了。**但对照组（改用 Cookie 里的令牌）同样是 403**，所以「改成先读 Cookie 就能好」这个判断**没有得到证实**。可能是探针用 CDP 设的 `csrftoken` Cookie 本身有问题，也可能另有原因，修的人要先在真浏览器里走一遍「退出 → 新标签页登录 → 回来改」，看 403 是哪一种（看 Django 日志里的 CSRF 失败原因）。离开不拦是 `pending()` 的逻辑，和 403 的原因无关，已经确认

### 12-2 文章保存的回答在路上丢了一次（新修订已经建了），之后这一页每次保存都被当成「别人改过」拒掉

- **严重度**：中（偏低：要网络恰好在服务器提交以后断掉才会碰到，但碰到以后一直存不上）
- **位置**：`static/js/autosave.js:236-254`（失败以后用同一张表单重试）、`content/drafts.py:29-42`（`stale_base`）、`backoffice/views/articles.py:172-173,190-191`；网站页面 `backoffice/views/pages.py:94-101` 等同理
- **问题**：216 加的 `X-Autosave-Key` 只解决「新建」的重试。对已有的文章，一次保存如果新建了修订（第一次改别人的稿、隔了 30 分钟、发布以后），回答丢了，表单里的 `latest_revision` 还是旧号；5 秒后重试，`stale_base` 发现号对不上，回「另一个人在你打开以后改过这篇……刷新页面」。之后每次保存都带着旧号，全部被拒。拒绝的回答 `failed = false`、`dirty = false`，所以 `beforeunload` 也不拦，用户照提示刷新，丢掉的正是他自己后来写的内容。提示说「另一个人」也不对
- **失败场景**：校园网信号不好，编辑改别人的一篇稿，第一次保存的回答丢了。之后写的半小时内容一次都没存上，状态栏一直说别人改过
- **怎么验证**：探针 B 段：站长打开种子文章的编辑页，用 DevTools 的 `Fetch` 在 response 阶段把第一次自动保存 POST 的回答 `failRequest`（这时服务器已经存了），等重试，读状态栏和隐藏框 `latest_revision`；再改一次标题，读状态栏，查库里最新修订
- **状态**：**已复现**（探针 B 段，真实输出）：
  ```
  打开时表单里的 latest_revision = 8
  拦下第一次自动保存的回答（服务器已回 200 ），让浏览器当成连接断了
  重试以后：状态栏 = 没有保存：另一个人在你打开以后改过这篇，你的改动没有存；刷新页面看一看现在的内容，再重新改。
  表单里的 latest_revision = 8
  再改一次：状态栏 = 没有保存：另一个人在你打开以后改过这篇，你的改动没有存；刷新页面看一看现在的内容，再重新改。
  这时离开页面会不会被拦 = False
  库里最新修订： 9 截图站长 截图攻略甲
  ```
  第一次的「甲」存进了修订 9；之后的「乙」被拒，页面上说是「另一个人」改的，离开也不拦

## 低

### 12-3 密钥框的自动保存竞态：重试或「接着再发」会把打了一半的密钥存进库，回答到了再把正在打字的框清空

- **位置**：`static/js/autosave.js:316-337`（`isText` 不含 `password`，所以 216 加的「正在打字 / 发出后又改过」两道判断都管不到密钥框，`values` 里的 `""` 直接写进框，框有焦点也写）、`:415-425`（`input` 跳过密钥，但 `new FormData(form)` 每次都把整张表单发出去）、`backoffice/views/settings.py:30-35`
- **问题**：设计 13.17 说密钥「离开框时才存，不在打字中途存半截」。实际上只要在打密钥的时候另一次保存被触发，比如上一次失败以后的退避重试到点了，或者 `again` 接着再发，`FormData` 就带着半截密钥发出去，服务器当成有效改动存下，回 `values.smtp_password = ""`，还在打字的框被清空
- **失败场景**：站长改了站点名称，网络抖动，保存失败，5 秒后重试；这 5 秒里他点进 SMTP 密码框开始打。重试把半截密码存进库，框被清空，他以为没打进去再打一遍，离开框时存的是第二遍。如果第二遍和第一遍拼起来不一样，库里存的就是错的
- **怎么验证**：在设置页把一次保存的回答拦成失败，5 秒内往 `smtp_password` 里写值但不触发 `change`，看重试请求体里有没有带上它，再看框有没有被清空
- **状态**：已核对代码

### 12-4 内置的 CodeMirror 5.65.15 有公开的 ReDoS（CVE-2025-6493，Markdown 模式）

- **位置**：`static/vendor/easymde/easymde.min.js`（里面写着 `.version="5.65.15"`）、`static/vendor/README.md`、`THIRD_PARTY_NOTICES.md:11`
- **问题**：CVE-2025-6493 影响 CodeMirror 5.65.20 及以前版本，在 `mode/markdown/markdown.js` 里，构造的 Markdown 能让正则灾难性回溯。EasyMDE 用的就是这个模式。上游不修 5.x，建议迁到 6。影响面只在编辑者自己的浏览器：投稿者能提交一篇构造过的正文，内容编辑在后台打开编辑页时标签页卡死；服务端渲染走 markdown-it，不受影响
- **怎么验证**：拿公开的 PoC 正文放进一篇文章的 body，在后台打开编辑页，看主线程卡多久
- **状态**：推测（版本号已核对；CVE 的说法来自 NVD 和 Red Hat 的公告，见文末来源；没有用 PoC 实测）

### 12-5 Django 6 给控件写的 `aria-describedby` 指向页面上不存在的 id，帮助文字和错误读屏都读不到

- **位置**：`templates/components/form_field.html`（帮助文字 `<div class="c-field__help">` 和错误 `<p class="c-field__error">` 都没写 `id="{{ field.auto_id }}_helptext"` / `_error`）、Django `forms/boundfield.py:298-313`（只要字段有 help_text 或错误，就自动加 `aria-describedby="id_x_helptext id_x_error"`）；后台走的 `backoffice/parts/fields.html` 也用这个组件。自动保存后加上去的错误（`autosave.js:357-363`）同样没有 id，也不改 `aria-invalid`。服务端渲染时留下的 `aria-invalid="true"`，`clearErrors()` 也不会去掉
- **问题**：全站带帮助文字的字段（签名「最多 30 字、不能放链接」、密钥「留空表示不修改」等）在读屏里聚焦时不会读出说明，整张提交以后的字段错误也不会关联到控件上
- **怎么验证**：探针 C 段：在 `/me/`、`/me/contacts/?new=1`、`/admin/settings/site/`、文章编辑页上找出 `aria-describedby` 指向的 id 中 `getElementById` 拿不到的；或者 `curl` 任意一页，搜 `_helptext"` 只出现在属性里
- **状态**：**已复现**（探针 C 段，真实输出）：`/me/` 有 3 个控件（`file`、`motto`、`show_rank`），`/admin/settings/site/` 有 24 个，文章编辑页有 8 个，它们的 `aria-describedby` 指向页面上不存在的 `id_*_helptext`；`/me/contacts/?new=1` 是 0 个

### 12-6 分队页、队伍编排页的卡片移动按钮只叫「A」「B」「缓冲」「散人池」，读屏分不清是谁的

- **位置**：`scrims/templates/scrims/admin/_card.html`（`data-move` 按钮）、`tournaments/templates/tournaments/admin/_card.html:9,11`
- **问题**：这是给键盘和读屏用的路径（scrim-split.js:211 的注释说的就是这个），但每张卡上的按钮名字都一样，没有 `aria-label="把 <昵称> 移到 A 队"`。10 个人就是 30 个一样的「A, 按钮」。和 210 F7（图片选择器）是同一类问题
- **状态**：已核对代码

### 12-7 队伍编排页拖完没点「保存编队」就离开，没有提醒

- **位置**：`static/js/tournament-teams.js`（全文没有 `beforeunload`，也没有「有改动」的状态）
- **问题**：设计 13.17 有意让这个页面保留按钮（会发信），但拖了半天的编排在点导航、刷新时直接丢掉，页面上也没有「有没保存的改动」的提示。分队页因为自动保存没有这个问题
- **状态**：已核对代码（设计没要求有提醒，算体验缺口；要不要做由用户定）

### 12-8 新建时走「已经建在这里了」（`retry`）那条路，丢掉了第一次回答本来要带回来的 `values` 和 `replace`

- **位置**：`core/middleware.py:207-219`（`retry` 回答里 `values`、`replace` 都是空的）、`static/js/autosave.js:283-287`
- **问题**：新文章第一次保存的回答丢了、走 `retry` 转到编辑地址以后，表单的 `latest_revision` 一直是空的（`stale_base` 对空值放行，这一页在下一次真正存下来之前没有并发保护）；「预览草稿」按钮（`[data-article-preview]`）、赛事和内战的「已经建成草稿……发布」提示（`[data-event-next]`）都不会出现，刷新以后才有。不会丢数据
- **状态**：已核对代码

### 12-9 零碎

- `static/js/autosave.js:472-483`：`form.__owFlushed = true` 设上以后一直不清。别的表单（比如带 `data-confirm` 的「改用默认头像」）先等存完再提交；如果用户在确认框里点了取消，下次再提交这张表单就跳过「先存完」，直接触发 `beforeunload` 的离开提醒。已核对代码
- `static/js/backoffice.js:128-131`：成员分组搜人的 `fetch` 不看 `response.ok`。会话失效时拿到的是登录页，`response.json()` 抛出未处理的拒绝，结果列表停在旧的，没有提示。已核对代码
- `static/js/backoffice.js:89-91`：`sendInline` 遇到网络错误时退回 `form.submit()` 整张重发。「加入」「移动」这类请求要是第一次其实已经到了服务器，会再做一次（服务端大概率会拦重复，没核对）。推测
- `static/js/loading.js:41-54`：前台点链接时自动保存还没存完，浏览器弹「离开此页？」，选「留下」以后加载条会一直跑到 15 秒超时。只影响外观。已核对代码
- `static/js/autosave.js:401-413`：分队页每换一次分队结果，就往 `savers` 里加一个新的 Saver，旧的（表单已经脱离页面）一直留着，`flushAll`、`anyPending` 每次都要遍历它们。不影响正确性
- `static/vendor/alpine.csp.min.js` 每个前台页面都加载（`templates/base.html:146`），但全仓库模板里没有 `x-data` 或任何 Alpine 指令。白加载一个库，不算缺陷，留给维护的人决定要不要删

## 查过没问题

- **XSS**：JS 里的 `innerHTML` / `outerHTML` 只有 5 处会写入 HTML（`autosave.js:296`、`backoffice.js:56,205`、`markdown-editor.js:80`，再加上几处写死的提示文字），收的都是服务端模板渲染、自动转义过的 HTML。`replace` 里手拼的片段（`articles.py:183`、`events.py:59`、`split_admin.py:187-196`）只含 `reverse()` 和数字。用户数据进 JS 的路径全部是 `textContent`、`confirm()`、`JSON.parse`（`data-ratings` 是 `json.dumps` 再经过属性转义）、`img.src`（服务端生成的缩略图地址）。全仓库 `|safe` 只有错误页的内联 CSS，`json_script` 只有排版页一处，没有 `autoescape off`。模板里 `href="{{ … }}"` 的来源都是 `reverse()`、`get_absolute_url` 或站内页面地址，`back_url` 全是 `reverse()`
- **CSP**：没有内联 `<script>`（只有 `type="speculationrules"`，CSP 用 `'inline-speculation-rules'` 放行），没有 `on*=` 和 `x-*` / `@click` 属性，模板里没有 `style=""`（邮件和错误页除外）。脚本改样式都走 CSSOM（`el.style.x = …`），不受 `style-src 'self'` 限制。Caddy 和 Django 的策略一致
- **210 的 F 条目在代码里都落实了**：F1（`state.js` 成功、失败、8 秒都会去掉骨架）、F2（永久失败不重试；网络错误、5xx、429 退避 5→60 秒；带文件的失败不自动重试）、F4（密钥存好后清空，但见 12-3）、F5（`response.redirected` 或 403 时不再把登录页塞进对话框）、F7（选择、清除按钮带上字段名）、F9（头像改用 `requestSubmit`，经过 `submit` 事件）、B5（发出后又改过的文字框不被回答盖掉）、S8（同一个 `data-autosave-queue` 的表单排队，等的是对方整条 `busy` 链，包括它接着再发的那一次；没有死锁）
- **`retry` 会不会死循环**：不会。`location` 全部来自 `reverse()`，`apply()` 把表单的 `action` 改成 `made`，下一次请求的 `request.path == made`，中间件就放行了。只有表单的 `action` 和页面地址不一致、而 `made` 正好等于页面地址时，才会原地反复 `retry`；会新建东西的那几张表单都不写 `action`，碰不到。失败重试是退避的、封顶 60 秒，401/403/404 和登录页不重试
- **htmx**：`allowEval = false`；CSRF 用 Cookie 里的令牌。`htmx:afterSwap` 在 htmx 2.0.10 里对新换进来的元素逐个触发（minified 源码核过），`setUp` 能接上新表单。连点「发表评论」排在后面的那次请求，表单已经被换掉，htmx 2 不会发出去。项目里没有 `hx-push-url` / `hx-boost`，htmx 不用 localStorage 存历史
- **事件监听在换片段时会不会泄漏**：全部委托在 `document` 上；`scrim-split.js` 用 `__wired` 防止重复接；绑在被换掉的元素上的 Sortable 和 click 监听会跟着元素一起被回收。`theme.js` 的菜单不在占位区里，不会被状态片段换掉
- **localStorage / sessionStorage**：`theme.js`、`arrival.js`、`loading.js` 每次读写都包在 try/catch 里，存储被禁用时照样能用
- **其余**：后台不加载 `app.js`、`loading.js`，不会出现确认框问两次或加载条不消失；`data-select-all` 只用在审核列表（不是自动保存表单），改值不发 `change` 没有影响；`target="_blank"` 全部带 `rel="noopener"`；推测规则排除了 `/admin/`、`/me/`、`/accounts/`、`/_fragments/`；`contextmenu.js` 不对 `javascript:` 链接提供菜单项，键盘可以操作；vendor 里的 htmx 2.0.10、Sortable 1.15.6、Alpine 3.17.1 没查到已知 CVE（只查了 CodeMirror 的，其余凭记忆，算推测）；`marked` 被 `previewRender` 换成了服务端预览，不参与渲染

- **手机布局**：探针 D 段在 375 宽、手机模式下打开 `screens.py` 的全部页面加 11 个公开页（首页、资讯、文章、赛事、内战、战队、成员、搜索、关于、登录、注册），真实输出是「53 个页面里 0 个比屏幕宽」（`documentElement.scrollWidth` 不大于视口宽）。没有逐张看截图，所以只确认了没有横向溢出

## 没来得及看

- `typography-preview.js` 和字体后台页的交互细节；EasyMDE 打开全屏、并排预览时会不会有 CSP 违规（`journey.py pages` 只开了页面，没点按钮）
- 各页面的颜色对比度、焦点顺序

来源（12-4）：[NVD CVE-2025-6493](https://nvd.nist.gov/vuln/detail/CVE-2025-6493)、[Red Hat CVE-2025-6493](https://access.redhat.com/security/cve/cve-2025-6493)
