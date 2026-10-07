# 10 · 测试与质量基建（新栈测试策略蓝本）

来源：认证/后台/测试调研代理。基线 `ec44ae4`。

## 3.1 数字汇总
- **测试：150 个测试文件、约 1750 个测试函数**。分布：core 63 文件/703 条、tournaments 16/225、accounts 18/157、content 15/155、scrims 9/122、teams 11/117、comments 2/61、backoffice 4/59、moderation 6/85、members 5/47、search 1/19。
- 守卫普查：**179 轮 254 个硬守卫**（core 64、tournaments 52、teams 39、accounts 33…），35 个未被测试抓到、补了 30 处测试；**210 轮全量 299 个**（新增 backoffice 26 个）+ 37 个软守卫；**181 轮 26 个软守卫**，11 个没抓到、9 处补测试、2 处有服务层兜底。基线全量约 1690 条 3 分钟（3 并行）。
- 变异机制：mutate_guards.py（AST 找「if 条件→拒绝/报错/4xx」守卫，替换成 False，并行跑「本应用测试→全量测试」）；mutate.py（把某轮补的守卫逐个改坏，先跑基线全绿，每改一处跑对应测试要求变红，恢复后再验证全绿——AGENTS.md 硬规则 7）。位于 handoff/rounds/179-guard-sweep/、181-soft-guards/、210-full-review/。

## 3.2 conftest.py（根目录）关键 fixture
- _cheap_password_hashing：测试用 MD5 哈希（conftest.py:21-27）。
- 固定测试库：TEST.NAME = data/test.sqlite3 文件库（非内存，才能断言 WAL PRAGMA）。
- 上传进临时目录；限流时钟冻结防跨分钟；renditions 内存缓存放空；事务测试结束必须迁回最新 schema。

## 3.3 标志性守卫测试（各守什么）
- **乱填参数**：core/tests/test_garbage_input.py:132,157——枚举全部路由，对 GET/POST 灌垃圾参数/超大 ID，以访客/成员/超管三身份访问，任何 500 都算失败；test_what_counts_as_an_id 钉住 core.converters.as_id 语义。
- **N+1 守卫**：core/tests/test_chapter15_audit.py（33 条测试）——对成员页/战队列表/赛事列表/内战详情/首页/栏目/文章页/搜索/我的报名/日历等每页断言查询数上限；另守首页体积预算（:441）、CSP 禁 inline/eval（:491）、真实页面无内联脚本（:510）、**限流数字与设计一致**（:527）、上传只收三种格式（:554）、预渲染页无 CSRF/个人信息（:569）、联系方式不上公开页（:591）、附录 A/B/C 常量逐一对照（:768-814）。
- **后台每个地址都过门**：core/tests/test_admin_wording.py:414 test_every_back_office_address_goes_through_the_door——遍历 /admin/ 全部 URL，断言每个视图都被 placed 包过、位置合法；backoffice/tests/test_door.py:119 用四种角色逐路由断言 403（>150 次拒绝）、:147 防止 404/403 泄露 ID 是否存在、:175 新建/删除另需权限；core/tests/test_admin_gates.py 以内容编辑身份验证各干部页拒绝。另有 test_documented_urls.py（设计里点名的 URL 必须还在且视图正确——防路由删改后静默落进 wagtail 兜底）。
- **CSP/外链拦截**：test_chapter15_audit.py:491,510 + core/tests/test_security_guards.py（SSRF：http/ftp 拒绝、内网 IP/解析到内网的域名/302 跳内网全拒；预渲染路径不越界；生产配置不全拒启动）。
- **深浅色 CSS**：core/tests/test_design_system.py:143（error.css 与主样式同 token）、:148 test_dark_mode_gives_every_palette_colour_a_dark_value（**每个调色板词在暗色块里都有对应值**，night-* 两模式同值）、:159（prefers-color-scheme 只出现一次，手选优先）；core/tests/test_colour_modes.py（切换脚本、夜带、双模式场景图）。
- 其它值得复刻的纪律：test_upstream_removed.py（已删应用不留痕）、test_check_script.py（CI 每条命令都在 check.sh 里）、test_admin_wording.py:78（po/mo 同步、后台无英文残留）、test_soft_guards.py、backoffice/tests/test_image_guards.py（投稿者不能动他人在同集合的图）。

## 3.4 浏览器测试
- scripts/journey.py 三模式（真实 Chromium + DevTools，每条 console error/未捕获异常/CSP 报告都算失败）：**默认模式**=新人第一晚（注册→worker 控制台邮件里读验证码→验证→加游戏 ID/联系方式→报内战→申请战队→首页「我的安排」看到内战）；**pages**=遍历项目自身全部路由，以访客/成员/超管三身份（后台仅超管）逐页打开看报错；**admin**=干部流程（再拉 10 人报名、内战分队页勾选生成队伍拖卡、赛事编队页建队）。
- scripts/screens.py：临时站+服务端造会话（不输密码）+ 无头 Chromium 截图约 40 个页面（前台各页、三封邮件样式页、后台 15 页），支持宽度/暗色参数。
- scripts/remote-check.sh：把工作树打成 git bundle 送测试机（IPv6 SSH 或端口转发），与 CI 同一套 + pytest 按每 CPU 一个 worktree 分片 + 并行 docker build，单锁排队、断线重连。
- scripts/check.sh 检查组（与 CI 同序）：uv sync → ruff check + format --check → tailwind build → pytest（可分片）→ makemigrations --check --dry-run → 生产环境变量下 manage.py check --deploy → render_error_pages + git diff --exit-code deploy/error_pages（错误页与模板一致）→（可选）docker build。

## 3.5 CI（.github/workflows/ci.yml，唯一工作流）
push(main)/PR → 单 job 7 步：checkout → setup-uv（py3.13，缓存）→ uv sync --frozen → ruff check+format → tailwind download_cli+build → uv run pytest → makemigrations --check → prod settings 的 check --deploy → 错误页渲染对比 git diff → docker build。无部署步骤、无浏览器测试（那些在测试机经 remote-check.sh 跑）。

## 给 Go/Vue 重构的直接结论

1. **认证可整体换 Go 自研**：保留 Argon2 PHC 兼容验证、单登录入口（废侧门）、按访客 IP 的限流数字（登录失败 10/m/ip + 5/300s/key 等）、改邮箱重认证、注销匿名化语义、导出清单的逐列取舍。
2. **Wagtail 的等价物清单**：页面树+修订+定时发布是最重的一块；图片库只剩集合权限+renditions 居中裁剪+WebP；正文已是 Markdown（渲染规则可直接搬）；Wagtail 管理界面、forms、documents、搜索推广在 Go 版全部不要。
3. **测试纪律的精髓**：路由级守卫测试（every address through the door / garbage input）、N+1 预算测试、设计数字钉死测试（附录对照）、变异式守卫普查（把每个 if 拒绝条件改坏验证测试变红）、真实浏览器三身份遍历——这套在 Go+Vue 里用 **route 遍历 + 查询计数包装 driver + Playwright** 可完整重建：
   - Go：表驱动单测 + httptest API 测试；查询计数用包装 driver；每页查询预算测试；
   - 变异：Go 生态的成熟工具缺位，用自制「改坏守卫跑测试」脚本（mutate.py 思路照搬）；
   - 浏览器：journey.py 三模式移植成 Playwright；screens.py 对拍截图；
   - CSP/体积：保留同款测试（script-src 'self'、无内联、首页 gzip 预算——Vue 后重谈数字）；
   - CI：双语言 job（Go: vet/staticcheck/govulncheck/test；Node: typecheck/lint/test/build），测试机 remote-check 模式照旧。
