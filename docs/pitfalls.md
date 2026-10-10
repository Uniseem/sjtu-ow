# 已知的坑

原 AGENTS 的踩坑记录集中在这里，按当前任务搜索，不必开工全读。旧站条目只用于对拍参照或授权修复，不解除旧站冻结。新发现追加在对应分组，注明轮次；发现旧记录有错时追加更正，保留原文。当前任务和阻塞只写 STATUS。

## 旧站、工具与验收经验

- **Alpine 是 CSP 构建**，HTML 属性里的表达式不会求值。交互用 `<details>` 或外部 JS 文件（020、032）
- **Wagtail 的兜底路由**让 `resolve()` 对任何路径都不抛异常。测地址存在要断言解析到的视图名（029）
- **字体切片必须可复现**：`TTFont(..., recalcTimestamp=False)`，否则同一个字体两次切出不同哈希（023）
- **邮件主题前缀由 `core.mail` 统一加**，业务代码写裸主题（026）
- **备份要找真正在用的数据库文件**：用 `core/dbfile.py` 的 `database_path()`，不是 `settings.DATABASE_PATH`（022）
- **计时测试在机器繁忙时会偶发失败**：6v6 分队 1 秒内、数据库被锁时 `/healthz` 1 秒内。并行跑测试或变异测试时注意（042）
- **`handoff/` 在 ruff 的排除列表里**（轮次报告要原样引用代码）。放在里面的脚本要指定路径单独检查
- **变异测试改回代码后**，如果文件大小和修改时间没变，Python 可能用旧的 `__pycache__`。改回后清一下缓存再跑（027）
- **预渲染**：从备份恢复后必须清空 `prerendered/`；开发环境默认关闭预渲染
- **别只用超级管理员测权限**：超级管理员能通过所有权限检查，用它测后台等于没测。至少要有一条用「能进后台、但不该有这个权限」的人（比如内容编辑）。059 补的测试里大约一半是这类（055 的内战管理员问题也是这样藏住的）
- **找「以后再接」的占位**：M2–M4 写代码时留了不少钩子和注释等后面的里程碑来接，已经发现四处没人回来接（055、056、059）。改一个功能时搜一下相关的 `M[0-9]`、「后续里程碑」、「placeholder」
- **只改模板时 `tailwind build` 会跳过**（「up to date」只看 CSS 入口文件）。模板里用了新的工具类，要 `tailwind build --force`，否则新类名不会进 `app.css`（065）
- **登录入口全站唯一**（218，217 复核 04-1）：Wagtail 自带的 `/wagtail/login/`、`/_util/login/` 直接调 Django 的认证，没有 allauth 的失败限流和邮箱验证，现在只做跳转（`accounts.views.login_door`）。以后装的任何应用带了登录页，`test_every_login_address_is_served_by_allauth_or_the_side_door_redirect` 会红；别为了「方便」再给哪个后台开一个不走 allauth 的登录口。守卫按 `resolve()` 看谁在处理，不看注册了什么：Wagtail 自己那两条仍然注册着，只是被前面的遮住
- **所有上传的图走 `core/uploads.py`**（219，217 复核 07-1/07-2/07-3）：EXIF 坏掉的图能解码、只在 Wagtail 生成缩略图时抛 `ValueError`，整页 500；原图原样存在公开的 `/media/original_images/`，GPS 跟着公开。新写的上传入口（表单、视图、管理命令）一律过 `clean_image`，别直接把 `UploadedFile` 交给 `Image(file=…)`。Wagtail 的图片表单在 `core/image_forms.py` 里统一过了（`WAGTAILIMAGES_IMAGE_FORM_BASE`），模型层不拦：脚本里 `Image.objects.create(file=…)` 不经过它。**Wagtail 8 删图片文件是排一个任务让 worker 去删**（`wagtail.tasks.delete_file_from_storage_task`），不是提交后马上删：测试里断言任务排了、再调 `.func(*args)` 执行，别断言文件马上不在了
- **Wagtail 的富文本不包在 `.rich-text` 里**。按 `.rich-text p` 写的样式从 M2 起就没生效过，文章段落、列表一直没样式（065 修正）。给正文写样式，直接挂在外层容器（`.article-body p`）上
- **在 `web` 里跑通不等于 `worker` 能跑**：两个容器用同一个镜像，但挂的卷不一样。053 起全量预渲染都是 `exec web` 跑的，worker 缺静态卷、事件触发的生成全部失败，11 轮没人发现（064）。验证 worker 做的事（预渲染、邮件），要在服务器上触发一次、看结果
- **删应用之前先看迁移依赖**：`tournaments/0004` 依赖 `integrations/0001`。lfg 是叶子应用可以整个删（066），`integrations` 不行，067 只删代码，包和迁移文件留作墓碑，新迁移删表。以后要删应用先 `grep -rn "<app>" */migrations/`
- **Windows 上跑测试要设 `PYTHONUTF8=1`**：几条测试用 `read_text()` 不带编码读中文文件，系统默认 GBK 会解码失败；`tailwind build` 也会打印一条 `UnicodeDecodeError`，但 CSS 照样生成。测试里比较路径要用 `as_posix()`，`str(path)` 在 Windows 上是反斜杠（080）。CI 是 Linux，没这个问题（067）
- **后台也是自己写的**（196 起，`docs/admin.md`）：`/admin/` 是 `backoffice/` 的页面，`/wagtail/` 是 Wagtail 的管理界面、只放超管进（`core.middleware.WagtailAdminCSPMiddleware` 把别人送回 `/admin/`）。新后台视图一律用 `backoffice.nav.placed(大类, 标签)` 包上，它就是门（没登录跳登录页、没 `access_admin` 给 403），漏了会被 `test_every_back_office_address_goes_through_the_door` 拦下；Wagtail 以前在后台里把 `PermissionDenied` 变成「跳回首页」，新后台直接 403，测试里断言 403。改了 `backoffice/` 的模板或脚本，跑一次 `journey.py pages` 和 `journey.py admin`（后者会在新后台写文章、用对话框选封面、发布）。Markdown 编辑器的工具栏图标在新后台里来自 `backoffice/templates/backoffice/parts/editor_icons.html`，`markdown-editor.js` 加新按钮时那里也要画一个，否则按钮是空的
- **改值的表单都自动保存**（202 起，设计 13.17）：新加后台或个人中心的编辑页，表单写 `data-autosave`、保存按钮写 `data-autosave-button`，视图认 `core.autosave.wants(request)` 回 JSON（规则在 `core/autosave.py`：有问题的字段不存、别的照存；跨字段的规则用表单的 `autosave_together` 指出哪些字段一起不存，不写就整张不存）。脚本改值不会自动触发事件：`backoffice.js` 的选图在改隐藏框后要 `dispatchEvent(new Event("change", {bubbles: true}))`，以后别的脚本改表单值也一样，否则不会自动保存；`journey.py` 里用脚本填表单的地方同样要发 `input` / `change`。表单校验看不见的数据库约束（条件里有表单外的字段，比如战队名只在没解散的队里唯一）要在表单里自己查，否则自动保存时是 500（202 补了后台战队名）
- **前台组件是自己写的**（074 起，设计 13.2）：`assets/css/input.css` 里的 `c-*` 组件和 `l-*` 布局，模板只用语义颜色（`text-fg-2`、`border-rule`）。**Tailwind 自带的色板关掉了**，`bg-orange-500` 这种类不会生成；077 起不再加载 daisyUI，模板里写 `btn`、`badge` 之类会被测试拦下。新组件先写进设计 13.2.7，再加到样张页 `/_styleguide/`
- **Linux 容器里截图看不到苹方和 DIN**：只有文泉驿，截出来和访客看到的差很多。074 从 Google Fonts 的仓库下载 Noto Sans SC、Barlow，用 fontconfig 在扫描时注册成 `PingFang SC`、`DIN Condensed`（配置在 074 报告末尾）。`runserver --noreload` 不会重新读模板，改了模板要重启
- **表格放在网格或弹性布局里会被拉高**（074）：行高被撑开到和旁边一栏一样。`c-table` 已经设了 `align-self: start`，自己写的表格也要注意
- **变异测试前先确认测试本身是绿的**：变异脚本只看「改坏后红不红」，基线已经红的话，每处变异都会显示「被抓到」。083 就这样出过一轮假结果。084 起的 `mutate.py` 先跑一遍基线，红了直接停（083）
- **内置浏览器面板在后台时不渲染动画帧**：`requestAnimationFrame` 不回调、CSS 过渡停在起点，动效看起来像坏了（081，当时的 `motion.js` 在 086 删了）。截图和量尺寸更可靠的办法是用无头 Edge 的调试端口：`Emulation.setEmulatedMedia` 切深浅色、`Emulation.setDeviceMetricsOverride` 切手机宽度、`Page.captureScreenshot` 带 `captureBeyondViewport` 截整页（086）；站点禁止被 iframe 嵌入
- **无头 Edge 的探测脚本要按配置目录名关进程**（106）：`msedge.exe` 的启动进程马上就退出，`terminate()`、`taskkill /T` 都关不掉真正的浏览器。上一次的实例会一直占着调试端口，下一次探测连上的其实是它和它的旧缓存，106 因此一度得出错误结论（清掉 48 个残留进程）。每次用空闲端口、单独的 `--user-data-dir`，结束时按目录名找进程关掉（`handoff/rounds/106-page-transitions/loadbar_probe.py` 的 `kill_profile`）
- **调试工具在跳转进行时会压住对页面的读取**（106）：点了链接以后 `Runtime.evaluate` 要等新页面加载完才返回，读不到旧页上发生的事。要看旧页（比如加载条），在 `window` 上挂一个更晚执行的点击监听取消跳转
- **内置浏览器面板会跑旧脚本、不做预渲染**（106）：开发服务器发静态文件不带 `Cache-Control`，面板按启发式缓存，改了 JS 刷新后还是旧的（看调用栈的行号就知道）；它也关掉了 Speculation Rules 的预渲染。验证脚本和预加载用无头 Edge
- **深浅两套颜色**（086 起，091 可以手动切换）：深色值写在 `input.css` 的 `:root { @variant dark { … } }` 里，覆盖 `@theme` 的同名变量。加新颜色要两处都写，漏写深色的测试会红；模板里别写只在浅色下成立的东西（白底图、黑色文字）。**组件里区分模式只用 `@variant dark`**，直接写 `@media (prefers-color-scheme: dark)` 的话，访客在页头选了浅色或深色时不生效（有测试数这个词只出现一次）。截图测模式时，无头浏览器的 `Emulation.setEmulatedMedia` 只模拟系统设置；要测手动选择，在页面里设 `localStorage['ow-theme']` 或 `<html data-theme>`
- **Django 的 `default` 过滤器会先算参数**：`{{ members|default:team.member_count }}` 即使 `members` 有值也会求 `team.member_count`，列表里每一项多查一次数据库（088）。参数有代价时用 `{% if %}`
- **前端脚本里别用 `DOMParser` 解析带 `style=""` 的 SVG**（091）：解析出的文档沿用页面的内容安全策略，每个 `style` 属性都报一次违规（校徽有 50 条）。要拆 SVG 就用字符串处理（现在校徽在服务端由 `core/emblem.py` 拆）
- **Django 的 `{# #}` 注释只能写一行**（091）：跨行的 `{# … #}` 会原样显示在页面上，多行用 `{% comment %}`
- **Windows 上改了 Python 文件后 `tailwind runserver` 可能卡死**（090、091 各两三次）：进程还在、端口不再响应，或者干脆退出。重启开发服务器就好；变异测试这类连续改文件的脚本跑完先确认服务器还活着
- **`tailwind runserver` 会改写 `static/css/app.css`**（091）：它的监视进程在你改任何被扫描的文件（包括 `.py`）后重新编译出**不压缩、保留 CSS 嵌套**的版本，覆盖掉 `tailwind build` 的压缩版。读 `app.css` 的测试要两种写法都认；要确定性地跑全量测试，先 `tailwind build --force`，跑完之前别改文件。**最稳的是跑全量前停掉开发服务器**：096–098 里开发服务器卡死重启后，它的监视进程好几次在测试中途重写 `app.css`，`test_body_text_rules_match_what_wagtail_renders` 就红了
- **挂载的数据卷只能清空、不能删**（102 发现，103 修了）：Compose 里 `/app/media`、`/app/prerendered` 都是挂载点，`shutil.rmtree` 删光里面的文件后删目录本身时报 `Device or resource busy`。102 的 `restore` 就这样换好了数据库、上传文件却全没了。现在 `restore` 用 `empty_folder()` 只清内容，再 `copytree(..., dirs_exist_ok=True)`；以后写会碰这些目录的代码也一样，测试里的临时目录删得掉，测不出来（103 的测试把 `os.rmdir` 换成对这两个目录报错）
- **从 Windows 打包文件传到服务器会带 CRLF**（105）：本机工作区是 CRLF（仓库里是 LF），`tar` 原样打包。Caddy、Python 照样能读，但按行匹配的脚本（`awk '/^\tadmin off$/'`）会对不上，105 生成 `Caddyfile.vps` 时 `trusted_proxies` 就这样漏插了一次。传上去后 `sed -i 's/\r$//'`，或者等提交推送后在服务器上 `git pull`。**二进制文件不能这样去 CRLF**（171）：演示站的 `/root/deploy_ship.sh` 原来只跳过 png、webp、jpg、woff2、mo，`favicon.ico` 被删掉 3 个字节，浏览器拿到的是坏图标；现在按扩展名跳过常见的二进制类型，其余用 `grep -I`（有 NUL 字节才当二进制）判断
- **Windows 上别用 `manage.py shell < 文件`**（102）：Windows 的管道不支持 `select`，Django 退回交互式控制台逐行执行，函数和循环中间的空行会把语句截断，脚本只跑了一半还不报错退出。本机用 `manage.py shell -c "exec(open(r'路径', encoding='utf-8').read())"`；服务器（Linux）上 `<` 没问题
- **本机推送 403**（101）：本机 `gh` 登录了两个 GitHub 账号，当前激活的不是 `Uniseem` 时，`git push` 会被拒（Permission denied）。不要切换全局账号，只给这一次推送指定凭据：`git -c credential.helper= -c 'credential.helper=!f() { test "$1" = get && echo username=Uniseem && echo "password=$(gh auth token -h github.com -u Uniseem)"; }; f' push origin main`
- **Git Bash 的 heredoc 会吃掉一层反斜杠**（092）：在 Bash 工具里用 `python - << 'EOF'` 跑内联脚本时，脚本源码里写的两个反斜杠加 n 到 Python 那里只剩一个，替换进文件的就成了真换行；正则里的反斜杠也会少一层。091、092 几次把测试文件写坏（字符串字面量被拆成两行）。改文件用编辑工具，或者先把脚本写成 `.py` 文件再运行
- **到测试机的长连接可能被半路掐断**（128）：连原来那台 `185.99.135.224` 时，输出一直在走、开着保活，`ssh` 照样在 1 分 53 秒、5 分 08 秒被断开，两头都说是对方断的，服务器上跟着连接的进程一起被杀。所以 `remote-check.sh` 让检查在服务器上脱离连接跑（`setsid`），本机每 3 秒用短连接取一次日志。在远程机器上跑长任务都这样做，别 `ssh host 长命令`
- **`manage.py tailwind download_cli` 每次都重新下载**（144）：django-tailwind-cli 这个命令是强制下载（112 MB），原来 `check.sh` 和 Dockerfile 每次都调，GitHub 一返回 503，检查和部署都失败。现在 Dockerfile 在 `COPY . .` 之前用 `deploy/fetch_tailwind_cli.py`（带重试）下载固定版本，这一层能缓存；`check.sh` 只在文件不在时才下载。升级 `TAILWIND_CLI_VERSION` 时 Dockerfile 的 `ARG` 要一起改（有测试比对）
- **测试里的密码哈希是 MD5**（128，根目录 `conftest.py`）：网站用 Argon2，每次哈希要 100 MB、几十毫秒，测试建几百个用户和登录，换掉后 pytest 快了一倍半。要测和哈希有关的东西，在那条测试里自己设 `settings.PASSWORD_HASHERS`
- **测试库是固定文件 `data/test.sqlite3`**（128）：两个 pytest 不能在同一个目录里同时跑。`scripts/pytest-shards.sh` 给每个分片一个 git worktree（各自的库、`prerendered/`、`.venv`）
- **`page.get_url()`、`page.url` 不带请求，在循环里就是 N+1**（163）：Wagtail 每次都去缓存里读站点根路径，本站的默认缓存是数据库表，一次调用一次查询。列表里用 `{% pageurl %}`（模板里有请求）或 `page.get_url(request)`。搜索就这样每篇命中的文章多查一次
- **`ArticlePage.objects…` 别再 `.specific()`**（163）：拿到的已经是文章本身，`.specific()` 让 Wagtail 再取一遍，前面写的 `select_related` 也跟着丢了
- **量查询数时，数据要覆盖页面上的每一类内容**（163）：临时探测给搜索只放了战队，结论「平的」；正式守卫放了文章才发现每篇多两次查询。`core/tests/test_chapter15_audit.py` 的 `assert_no_n_plus_one` 比 3 份和 10 份数据
- **Wagtail 自带的复制页拿原对象预填表单**（159）：表单提交到新建地址时没事，但直接提交回复制地址的话，状态、发布时间这些不在表单里的字段会一起带进新的一条。本站的内战、赛事复制改成只照抄列出的字段新建对象（`core.services.copy_ahead`），别的模型要开复制也照这样做
- **编号一律过一道关**（166、167）：地址里写 `<id:pk>` 不写 `<int:pk>`（最多 18 位，有测试拦 `<int:`）；从表单或查询参数里取的编号用 `core.converters.as_id()`，不是编号就是 None。直接把 `request.POST.get(...)` 交给 `pk=` 的话，「abc」是 `ValueError`，20 位数字查一对一外键（Wagtail 页面）是 `OverflowError`，都是 500。`core/tests/test_garbage_input.py` 把全站地址乱填一遍，新加的页面出 500 它会红
- **Wagtail 的标题面板在表单里没有 slug 字段时会留一个空选择器**（169）：它照样挂上 `w-sync` 控制器，`data-w-sync-target-value` 是空的，浏览器里报「Error connecting controller」。196 起写文章用新后台自己的表单，Wagtail 的编辑器只给超管（他们的表单总有 slug），当时的 `content.panels.TitlePanel` 删了；以后要是又让别人进 `/wagtail/` 编辑页面，这个坑还在
- **用了 `account/_form.html` 就别再自己写 `form.non_field_errors`**（168）：这个共用的表单片段已经显示整表单的错误，战队的申请、新建、管理页又写了一遍，同一句话显示两次。有测试拦
- **`querydict_from_html` 的两个坑**（159）：没写 `value` 的勾选框读出来是空字符串，Django 会当成没勾（浏览器发的是 `on`，测试里按 `checked` 改回 `on`）；Django 在 `<textarea>` 后面加一个换行，读出来的值开头多一个换行，比较前 `strip()`
- **别用一个短词断言页面里「没有」某样东西**（175）：`"cdn" not in html.lower()` 会碰上页面里的 CSRF 令牌、内容安全策略随机串，偶尔就红（171 的 CI 这样红过一次）。断言具体的结构，比如没有 `src="https://…"` 的 `<script>`
- **正文和说明是 Markdown**（192 起，设计 5.2）：渲染只走 `content/markdown.py`，别在别处再写一个；测试里建文章直接写 `body="正文"`，不再是 `[("paragraph", …)]`。`content/legacy_body.py` 和 `content/blocks.py` 是迁移要用的，不能删。后台编辑器 EasyMDE 的样式表是表单资源；覆盖它的规则在 `static/css/markdown-editor.css`（196 起由控件带上，排在 EasyMDE 的后面），前面都加了 `.md-field` 提高优先级，新加的也要加
- **后台的八个大类**（193 起，196 重写）：193 那版靠 `core/admin_sections.py` 按网址前缀往 Wagtail 的界面里插标签条，196 整个删了；现在大类和标签在 `backoffice/nav.py`，视图用 `placed()` 自己声明在哪（见上面「后台也是自己写的」）
- **`htmx.ajax()` 的 Promise 只在网络错误时 reject**（215）：429、5xx 照样 resolve（只是不换内容），HTMX 没加载上时根本没有 Promise。只写 `.then(成功)` 的话，断网、脚本被拦时界面会卡在中间状态（`state.js` 的骨架就这样一直挂着）。收尾的事写 `.then(done, done)`，再加一个超时兜底。在浏览器里验证这类「一闪而过」的状态别从外面轮询（失败几十毫秒就结束，轮询看不到），用 `Page.addScriptToEvaluateOnNewDocument` 挂一个 MutationObserver 让页面自己记时间（`handoff/rounds/215-caddy-and-prerender/f1_probe.py`）
- **别用 `ssh 服务器 'bash -s' < 本机脚本` 跑含 `docker compose exec` 的脚本**（215）：`exec -T` 会把标准输入里剩下的脚本当成自己的输入读掉，后面的命令一条都不执行，退出码还是 0。215 升级正式站时就这样只做了备份、没部署。先 `scp` 脚本上去，再 `ssh 服务器 'bash /root/脚本.sh < /dev/null'`
- **空的数据卷每次挂载都会被 Docker 改回镜像里挂载点的属主**（216）：镜像 216 起以 `app`（uid 10001）运行。演练「旧数据卷属于 root」时只把空目录改成 root，一挂上又变回 `app`、照样能写，差点得出「升级不用交接」的错误结论；卷里有文件时才保持原属主。正式站的卷都有文件，所以 docs/legacy-guide.md「升级到 216」那步 `chown` 不能省。模拟旧卷要先往卷里放文件再改属主（`handoff/rounds/216-review-lows/c10_drill.sh`）
- **交接数据卷前先停 `web`、`worker`**（216）：只 `chown` 不停容器的话，旧容器（root）在交接和启动新容器之间还会写出新文件（预渲染页、`-wal`、上传），新镜像又写不进。顺序是 `build` → `stop web worker` → 用新镜像 `run --user root … chown` → `migrate` → `up -d`；之后 `find /app/... ! -user app` 应为 0
- **看容器里的进程以谁运行，别用 `docker top -eo user,args`**（216）：少了 PID 列，Docker 报「Couldn't find PID field」，而写成 `! docker top … | grep -q root` 的检查会因为命令失败「白过」。读容器里的 `/proc/1/status`（`grep '^Uid:'`）
- **变异脚本要改的那行在文件里出现两次时，会改到别处**（216）：`mutate.py` 用 `replace(old, new, 1)` 只换第一处；216「不能移除队长」的 `if membership.is_captain:` 在 `teams/services.py` 里有两处，变异改到了别的函数，测试照样绿，看起来像「没抓到」。写变异时把原文写长到只命中一处（带上相邻的注释或下一行），写完先数一遍出现次数
- **JS 的子串守卫别只查一个词**（216）：F5 的测试只查脚本里有没有 `response.redirected`，这个词在错误标记里也出现，把判断条件改坏照样绿。要查就查完整的条件（`if (!response.ok || response.redirected) {`）并断言它在关键调用之前；这类测试本来就抓不到逻辑错（217 16-3），行为靠 `journey.py` 和测试机上的浏览器探针
- **验证过邮箱的测试用户会被自动放进「投稿者」组**（216、217）：投稿者能发布文章、能传图。要测「能进后台但不能发布」「管理员自己的传图权限」时，测试用户别给验证过的邮箱，否则测试因为投稿者的权限变绿，测的不是要测的东西
- **`handoff/` 下的复现脚本不进 CI**（217）：复核代理的复现脚本断言的是「问题还在」，217 有几个名字正好匹配 `*_tests.py`，被 CI 收进去跑红了。`pyproject.toml` 的 `norecursedirs` 已排除 `handoff`；复现时指定路径跑（`remote-check.sh run uv run pytest -q handoff/…/文件.py`，指定路径时照样收集）。以后的复现脚本也放 `handoff/rounds/<轮次>/` 下
- **很多代理同时用测试机时会排长队**（217）：`remote-check.sh` 同一时间只跑一个，16 个复核代理各排几次复现，后面的等十几分钟；收尾时还排着的结果就拿不到了。派多个代理时让它们先读代码、只给最关键的几条上测试机，或者把复现合成一个脚本；长的变异普查在锁外单独的工作树里跑（docs/development.md「验收纪律」）。**别用 `| tail -N` 截输出**：13 号代理截掉了前面打印的数字，复现结论少了一半
- **跑完浏览器和演练脚本要收进程**（215）：测试机上留下过一天前的开发服务器、worker、Chromium 和 214 的演练脚本，父进程早没了。脚本里起的子进程要在 `finally` 里 `terminate()` 并等待，Docker 演练要 `trap … EXIT` 删容器和卷；发现孤儿时按 PID 逐个 `kill -TERM`（看 `ps -eo pid,ppid,etime,args`，`ppid` 是 1 的那些），别碰正在跑的那组
- **`transaction=True` 的测试提交的缓存行不会被清掉**（217 16-1）：`--reuse-db` 下下一次 pytest 还看得到，worker 心跳、限流计数这类缓存会让顺序靠后的测试偶发红。新写这类测试时在前后删掉自己用的缓存键（216 的 A10 线程测试就是这样做的）
- **和时间有关的断言要固定到整分**（217 16-13）：`test_autosave_events` 里一条比较「复制来的时间」，一边带微秒、一边被表单截到分钟，碰上就红（217 的 CI 红过一次）。造时间时用 `replace(second=0, microsecond=0)`
- **刚推送就 `gh run watch` 可能等的是上一次运行**（217）：新运行还没出现在列表里时取到的是旧的编号，或者 `watch` 提前退出。用后台循环等最新一条的 `status` 变成 `completed` 再读结论
- **本地全绿不等于 CI 全绿**：CI 机器上没有 gitignore 掉的编译产物，磁盘、时区、速度也和本地不同。仓库 042 轮之前从没在 GitHub 上跑过 CI，第一次跑就红了三条（044）。推送后要看 CI 结果

## 新栈

- **Vue SSR 的输出里混着片段注释**（233）：`v-for`/插槽插进来的文本两边有 `<!--[-->`/`<!--]-->`，`expect(html).toContain('>首页</a>')` 这种子串断言配不上。断言前先 `replace(/<!--.*?-->/g, "")`，或者只断言开标签里的属性。Vite 的 `--ssrManifest` 写的是 `ssr-manifest.json`（资源映射），不是 `manifest.json`（块依赖图，`build.manifest: true` 才写）——拼页面要的是后者
- **客户端要用 `createSSRApp` 才是激活**（261）：`createApp(...).mount()` 会先把容器 `textContent` 清空再画一遍（Vue 3.5 的 `runtime-dom`），看起来和激活一样，激活不一致永远测不出来。233–260 的 `entry-client` 就是这样，`browser-check` 的「激活」一项一直是白过的
- **`/api/images/{id}` 返回的是图片信息的 JSON，不是图**（261）：拿它当 `<img src>` 全是坏图。出图走 `/media/r/<编号>/<规格>.webp`（规格只认 `media.AllowedSpecs`），正文里旧的 `/media/images/*` 照旧
- **前台的状态码别靠页面自己判断**（261）：260 的页面在 `load` 里 `catch {}` 把接口的 401/404 吞成 `null`，于是不存在的战队是 200 加一句「不存在」、访客能打开 `/me/`。`load` 不吞错误，交给 `server.ts` 按状态码分流
- **测试机的 `go test` 会用缓存，依赖日期的测试在那里一直「绿」**（262）：日历订阅测试的数据钉在 10-09、`Serve` 用墙上的钟，10-10 起其实已经红了，测试机整组显示 `(cached)` 照样过，只有 CI 红。业务代码取「现在」走 `ctx.Now()` 或注入的 `clock.Clock`，别直接 `time.Now()`；改了日期相关的东西，单条跑加 `-count=1`
- **新栈和旧站别用同一个 Compose 项目名和服务名**（265）：259 的新栈也叫 `sjtu-ow`、也有 `web`、`worker`，构建时把旧站镜像的标签 `sjtu-ow-web:latest` 占了，回滚时 `up -d` 起不来旧站，只能重新构建。割接前先 `docker tag sjtu-ow-web:latest sjtu-ow-web:legacy`，新栈换个项目名（`docs/cutover.md` 第 5 节）
- **Caddy 的 `redir` 第一个参数以 `/` 开头会被当成匹配条件**（263）：`redir /static/img/favicon.ico 301` 不是「跳到这个地址」，而是「对这个路径跳到 301」，图标地址一直落到 SSR。要写 `redir * /目标 301`。改了 `deploy/Caddyfile.new` 就跑 `bash scripts/remote-check.sh run bash e2e/caddy/smoke.sh`（真 Caddy 容器 + 桩服务，逐条验路由和头），只读配置看不出这类错
- **转给上游的访客 IP 用 `{client_ip}`，不用 `{remote_host}`**（263）：正式站前面有用户的反代，`{remote_host}` 是反代的地址，Go 的限流和失败锁就成了全站共用一个计数。`{client_ip}` 认全局的 `trusted_proxies`
- **「200 OK」不等于页面对**（261）：260 拿「公网实测渲染 200」当验收，文章页 404、半数页面只有标题都没发现。前台的完成要和旧站对拍（`docs/frontend-migration.md` 第 9 节）
- **`page-data` 在 SPA 换页时先删旧键再填新值**（275）：`entry-client` 的换页是「删掉上一页的键、assign 新页的键」，旧页面组件在卸载前会重渲染，直接读键的 computed 会撞上 undefined（browser-check 抓到过 `reading 'stats'`）。页面的 inject 一律可空、computed 全程可选链或空形状兜底（`StandardPage.vue` 是写法样板）；守卫是 `browser-check.mjs` 的换页序列，改了页面数据读取就跑它
