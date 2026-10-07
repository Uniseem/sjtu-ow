# 220 实现报告（M0 的五个实验）

## 结论

**五个实验都不推翻 12 号文档的架构，不需要回头重新拍板 D1–D4。** 三个通过（E1、E3、E4），两个有条件通过（E2、E5）；E3 另有一条实现要求（flock）。条件都是「实现时这样写」，不是「换方案」。实验里发现了 **4 处要改 12 号文档的地方**（下面「对 12 号文档的修订」），在 221 写设计 v8.0 时一并改。

| 实验 | 结论 | 一句话 |
|---|---|---|
| E1 薄 SSR + 严格 CSP | **通过** | Vue 3 SSR + 激活在 `script-src 'self'`、零内联、零 `style=` 下跑通；客户端导航、无脚本横幅、404 都对 |
| E2 纯 Go 的 WebP | **有条件通过** | 比 libwebp 慢 3–5 倍；主图缩到 2560 宽、方法 2、缩略图懒生成，就在预算内。保留换回 cgo libwebp 的口子 |
| E3 SQLite 并发写 | **通过（加一条）** | 不丢更新、不坏；极端压力下 SQLite 自己的忙等不公平，**写事务前加 flock** 后一次 busy 都没有 |
| E4 Markdown 对拍 | **通过** | goldmark + 约 420 行变换，346 份文档 345 份和 markdown-it 一致，剩一处 `~~~` 是 markdown-it 的怪癖 |
| E5 CodeMirror 6 | **有条件通过** | 直接放进页面在严格 CSP 下**没有样式**；**挂进 ShadowRoot 就完全正常**，零违规 |

## 逐个实验

每个实验的原始数字在各自目录的 `RESULTS.txt`，能重跑的程序和脚本都在目录里。

### E1 薄 SSR + 严格 CSP（`e1-ssr-csp/`）

- **做了什么**：Vue 3.5 + vue-router 4 + @unhead/vue 2 + Vite 7，约 60 行的 Node 服务做 SSR 和静态文件，模拟 Go 接口；每个响应都带 12 号文档 6.9 的那条 CSP（`script-src 'self'`、`style-src 'self'`……）。用真 Chrome（无头，前台）通过 DevTools 协议跑 `check.mjs`
- **结果**：激活正常（按钮点得动、`js-ready` 加上）；控制台没有 CSP 违规、没有激活不一致警告（构建时打开了 `__VUE_PROD_HYDRATION_MISMATCH_DETAILS__`，不一致会大声报）；对照组确认策略真的开着（注入的内联脚本不跑、`style=` 属性和 `<style>` 元素被拦，`el.style.color=` 这种 CSSOM 写法不受影响）；客户端换页（loader 在浏览器里跑、`<title>` 和 `og:title` 更新）和后退都在同一个文档里完成，零违规；直接请求第二条路由也能激活；关掉脚本（`?nojs=1`）页面照样能读，**纯 CSS 的横幅 8 秒后出现**（6.10 的做法有效）；未知路径 404
- **体积**：JS gzip 48.3 KB（Vue + 路由 + head + 实验页面，单块），HTML 1 KB；真 `app.css` 现在约 19 KB。预算（JS ≤ 120 KB、整页 ≤ 300 KB）宽裕
- **速度**：一个 Node 进程，页面很小，所以只能说明框架开销：并发 1 时每页 0.4 毫秒，并发 10 时 3600 页/秒（p95 7 毫秒）。服务器内存跑完 5000 个请求后 310 MB（Node 堆在回收前会涨，容器要设 `--max-old-space-size`）
- **没验证**：WebKit、iOS 15 Safari、微信内置浏览器（M2 用 Playwright 的 WebKit 补）；真实页面的复杂度（真页面比实验页大几十倍，渲染时间会涨，但量级差得远）
- **顺带发现**：unhead 自己会写 `<meta charset>` 和 `viewport`，模板里不能再写，否则重复

### E2 纯 Go 的 WebP（`e2-webp/`）

- **做了什么**：`gen2brain/webp` v0.6.4（`CGO_ENABLED=0 go build -tags nodynamic`，7 MB 静态二进制），一张真照片拉成 4000×3000「手机照片」（加了传感器噪点，3.1 MB 的 JPEG）。走 12 号文档 5.13 的流程：解码 JPEG → 母版 WebP → 解码母版 → 四种缩略图。同一份 JPEG 另用 Pillow（C 的 libwebp）跑一遍作对照。本机（Mac arm64）和测试机（amd64、4 核）各跑一遍，取 5 次中位数

| 步骤 | 纯 Go（Mac / 测试机） | libwebp（Mac / 测试机） |
|---|---|---|
| 母版 q90，4000 宽，方法 4 | 3.3 s / 4.9 s | 1.0 s / 0.95 s |
| 母版 q90，2560 宽，方法 4 | 1.1 s / 1.7 s | 0.36 s / 0.36 s |
| 母版 q90，2560 宽，方法 2 | 0.38 s / 0.60 s | 0.14 s / 0.17 s |
| 缩略图 fill-2400×1350（缩放+编码） | 0.68 s / 1.08 s（2560 母版，方法 4） | 编码 0.16 / 0.19 s |
| 缩略图 fill-400×400 | 0.14 s / 0.18 s | — |
| 整条流水线（解码+母版+解码+4 张缩略图） | 4000 宽方法 4：5.3 s / 7.8 s；2560 宽方法 2：1.2 s / 1.75 s | — |

- 输出大小和 libwebp 相差不到 1%。内存：一张 1200 万像素的图，峰值常驻内存 710 MB
- **条件**：① 母版长边压到 **2560**（站上最大的缩略图 2400 宽，4000 宽的母版白占 3 倍时间和内存）；② 母版和缩略图用方法 2（大小多约 5%，快 3 倍）；③ 缩略图不在上传请求里全部生成，**首次被请求时在信号量（1 个）里生成并缓存一年**（12 号文档 5.13 本来就这么写）；④ 编码放在一个接口后面，**将来生产里首次缩略图的 p95 超过 1 秒，就换成 cgo 的 libwebp**（BSD），不改别的代码
- 这一条没有「不行」，但比 12 号文档写的（「2400×1350 一张够快」）慢得多：纯 Go 版是 libwebp 的 3–5 倍。上传量按每人每天 40 张封顶（219），这个慢度可以接受

### E3 SQLite 并发写（`e3-sqlite/`）

- **做了什么**：`modernc.org/sqlite` v1.60.1，DSN `_txlock=immediate`、`busy_timeout(5000)`、WAL。每一步：开 IMMEDIATE 事务、读计数器、停一小会儿（模拟「先检查再写」）、写计数器+1 和一行日志、提交。正确性判据：计数器 == 日志行数 == 成功的步数。进程内写池 `MaxOpenConns(1)`，另有只读池的读协程一直在读
- **本机**（4 进程 × 1000 步）：4000/4000，0 失败，读 120 万次 0 失败。**对照组**（普通 `BEGIN`，其余不变）：3100/4000 步立刻 `SQLITE_BUSY`——读完再升级写锁不会等。这证明 `IMMEDIATE` 是必须的，不是装饰
- **测试机**（amd64，4 核），一开始读协程空转，把写协程饿死了（速率只有本机的 1/8），限速后：
  - 2 个进程（api + worker）、事务里停 200 微秒、各 5000 步：9999/10000 成功，**有 1 步等了 5 秒后 `SQLITE_BUSY`**；
  - 2 个进程、事务里停 20 毫秒：400/400；
  - 8 个进程、20 毫秒（极端）：792/800，8 步在 5 秒后 `SQLITE_BUSY`，最长等了 14.9 秒；
  - **任何一种情况计数器都等于成功的步数，没有丢更新，没有损坏**
- **原因**：SQLite 的忙等是轮询，不排队；一个一直在写的进程能让另一个等过 `busy_timeout`。这是 SQLite 的已知特性，不是驱动的毛病
- **加一条（flock）**：每个写事务前先对 `<库>.wlock` 拿一个 `flock(2)`（Linux 上的等待者排队），提交后放。同样的负载：2 进程 10000/10000，8 进程 800/800，**零 busy**，最长一步等了 5.4 秒（八个进程抢）。单进程写事务的上限在这台机器上约 700 个/秒，比需求（峰值每秒十来个写）高两个数量级
- **条件**：`WriteTx` 的实现是「flock → `BEGIN IMMEDIATE` → 提交 → 放锁」，`busy_timeout` 留作兜底；写进程限两个（api、worker）；看门狗照 12 号文档 5.6

### E4 Markdown 对拍（`e4-goldmark/`）

- **做了什么**：goldmark v1.8.6 + 抽象语法树变换 + 节点渲染（`render.go`，约 420 行）复现 `content/markdown.py` 的规则：原始 HTML 当文本、单换行即换行、`#`/`##` → h2 和 `###` 以下 → h3、单独成行的图片 → 图和图注（只认本站图）、单独成行的 B 站链接 → 播放器（bvid 只认长得像的，短链只查本地缓存表）、裸地址变链接（同样的中文标点截断和结尾标点剥离）、引用末行「——」出处、表格外套滚动容器、不安全链接保持文本、统计图片和视频数。对拍语料 346 份：4 份取自现有测试、262 份是仓库自己的 Markdown 文档按 `##` 切开（表格、嵌套列表、引用、链接、删除线、代码都有）、80 份专门写的刁钻输入。两边输出解析成 HTML 再写回成统一形态（标签、属性排序、块之间的空白去掉）后比较。**语料里没有正式站的文章**（本轮不碰正式站）
- **结果**：第一版 300/313 一致，13 处差异全是删除线 `<del>`（markdown-it 写 `<s>`）。加了 30 份刁钻输入、修了三处以后 **345/346 一致**：单波浪线 `~x~` 在 goldmark 的 GFM 里是删除线、markdown-it 里不是（改成自己的行内解析器，要两个）；图注里的行内代码 markdown-it 会丢掉、我保留了（改成一致）。**剩下的一处**：三个波浪线 `~~~三个~~~`，markdown-it 写成 `~<s>三个</s>~`，我这边保持原样，是 markdown-it 的怪癖，没人这样写，**声明为有意的差异**
- **对照**：把标题规则关掉，同一套对拍报 50 处差异，说明对拍确实看得见问题
- **速度**：346 份共 1139 KB 的 Markdown，goldmark 解析加渲染总共 24 毫秒
- **没验证**：正式站的真实文章（M4 在正式站备份上再对拍一次，12 号文档 5.12 本来就这么写）、B 站短链 `b23.tv` 的解析往返（那是 worker 的事）、逐字节一致（这里比的是解析后的 HTML）

### E5 CodeMirror 6 在严格 CSP 下（`e5-codemirror/`）

- **做了什么**：CodeMirror 6（view 6.43、state 6.7、commands 6.11、language 6.13、lang-markdown 6.5，都是 MIT），Vite 构建，在 `style-src 'self'`（没有 `unsafe-inline`、没有 nonce）下，真 Chrome 通过 DevTools 协议验证；工具栏按钮（粗体、二级标题、引用、撤销）在编辑器外面，通过事务改文档
- **直接放进页面（现在 EasyMDE 的用法）：没有样式。** style-mod 往 `document` 里插一个 `<style>` 元素，被策略拦下（`style-src-elem` 违规，控制台报错）。`.cm-editor` 是 `display:block`、`.cm-content` 是 `white-space:normal`、没有主题、没有高亮（`screenshot-document-root.png`）。输入、工具栏、撤销的逻辑都还能用，只是样子是坏的。**这一条和 12 号文档 6.8 的说法不符**（那里说它用可构造样式表、不行再放开 `style-src`）
- **挂进 ShadowRoot：完全正常。** `new EditorView({root: shadowRoot, parent: shadowRoot})`：style-mod 的源码（`style-mod.js` 里 `if (!root.head && root.adoptedStyleSheets …)`）只有根不是 Document 时才用可构造样式表。实测 `document.adoptedStyleSheets` 为 1、`<style>` 为 0，样式齐全（`display:flex`、`break-spaces`、我们的 `EditorView.theme`、markdown 高亮），**零违规**；用 `Input.insertText` 输入中文、选区、工具栏三个按钮、撤销都对（`screenshot-shadow-root.png`）
- **条件**：编辑器一律挂进 ShadowRoot；需要浏览器支持 `adoptedStyleSheets`（Chrome 73+、Firefox 101+、Safari 16.4+，后台是干部用电脑的工具）；页面的 CSS 选择器进不了 ShadowRoot，编辑器主题用 `EditorView.theme` 写，站点的 CSS 变量会继承进去；万一遇到不支持的浏览器，退路是只给 `/admin` 放开 `style-src-elem 'unsafe-inline'`（`style-src-attr` 仍然 `none`）
- **体积**：502 KB，gzip 后 174 KB（lang-markdown 把 HTML、CSS、JS 的语言包也带进来了）。只在文章、页面、赛事、内战的编辑页懒加载，后台可以接受
- **顺带发现**：`@codemirror/language` 6.13.0 的发布包里 `import` 了 `@codemirror/streamparser`，却没写进它的依赖，直接 `npm install` 构建会失败；要显式加这个依赖、提交锁文件、锁版本
- **没验证**：真实中文输入法（拼音）的组合输入、Safari、Firefox、手机

## 对 12 号文档的修订（221 写设计 v8.0 时落实）

1. **5.6 数据库访问**：`WriteTx` 写成「flock `<库>.wlock` → `BEGIN IMMEDIATE` → 提交 → 放锁」，`busy_timeout` 作兜底；写进程只有 api 和 worker 两个；单写者吞吐上限约 700 事务/秒（4 核机器）。**新增不变量测试**：两个进程各开几个协程压写，计数器等于成功步数、零 `SQLITE_BUSY`
2. **5.13 图片**：母版长边 **2560**（原写 4000）；编码方法 2；缩略图首次请求时在信号量里生成；编码接口留出换 cgo libwebp 的口子，换的判据是「首次缩略图 p95 > 1 秒」。上传请求的耗时预算：解码 + 母版约 1 秒（测试机）
3. **6.8 后台 SPA**：编辑器**必须**挂进 ShadowRoot（原写「可构造样式表，不行再放开」）；写明 CodeMirror 的依赖要显式声明 `@codemirror/streamparser` 并锁版本；`/admin` 的退路是 `style-src-elem 'unsafe-inline'`
4. **6.2 SSR 服务**：模板里不写 `<meta charset>` 和 `viewport`（unhead 写）；容器设 Node 堆上限；`__VUE_PROD_HYDRATION_MISMATCH_DETAILS__` 在 CI 的浏览器测试里打开，激活不一致直接红
5. 5.12 Markdown：补两条规则——删除线要两个波浪线；图注里的行内代码不进图注。对拍的语料和比较程序（`e4-goldmark/`）直接成为 M4 的黄金用例起点

## 验收输出

- E1：`node check.mjs`（真 Chrome）的完整 JSON 输出见 `e1-ssr-csp/RESULTS.txt` 的摘要；`load.mjs` 的三行速度数字
- E2、E3：本机和测试机的原始数字在各自 `RESULTS.txt`
- E4：`go run .` 末行 `total identical 345 different 1 of 346 documents; goldmark rendered 1139 KB of Markdown in 24ms`
- E5：`node check.mjs` 的 JSON：文档根 `violations: ["style-src-elem inline"]`，ShadowRoot `violations: []`
- 整组检查（`bash scripts/remote-check.sh`，测试机，退出码 0）：ruff 通过；pytest 2163 条分 4 片全绿（541、541、541、540）；迁移无变化；生产配置无问题；错误页和模板一致；Docker 镜像构建成功。本轮没有改产品代码，这一遍只证明新增的实验文件没有惊动仓库自己的测试

## 设计偏差

无（本轮没有改 `docs/design.md`；它在 221 里改）。

## 未完成 / 顺带发现 / 需要确认

1. **实验用的依赖都只在各自目录里**（`node_modules/` 和 Go 缓存不进仓库，锁文件进），它们的许可证我逐个查了：Vue、vue-router、unhead、Vite、@vitejs/plugin-vue、CodeMirror 6 全家、style-mod、goldmark 是 MIT；modernc.org/sqlite、golang.org/x/image、x/net 是 BSD-3；gen2brain/webp 是 MIT，它带的 purego 是 Apache-2.0。符合硬规则 5（没有 GPL/AGPL）。**正式采用要等 M1、M2 各自开工时按硬规则 5 再确认一次**
2. E1 的真实页面复杂度、WebKit、微信浏览器没测；E5 的中文输入法没测；E4 没用正式站文章。这些是 M2、M4、M8 要补的，不是 M0 的阻碍
3. 测试机上留了几个文件在 `/tmp`，用完删了；没有留下进程
4. 218 的 crontab 和 219 的 `scrub_originals` 还在等你点头登录正式站（STATUS 里写着）

## 改动文件

只有 `handoff/rounds/220-m0-experiments/` 下的东西（五个实验目录、`request.md`、本报告、`review.md`、`.gitignore`）和 `handoff/STATUS.md`。
