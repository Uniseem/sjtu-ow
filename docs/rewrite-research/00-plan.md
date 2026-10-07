# 00 · 重构计划：前端 Vue 3 + 后端 Go

（2026-10-07 定稿于对话，随调研文档一起存档；执行前需先拍板「待拍板的 8 件事」。）

## 一、调研结论（现状全景）

| 维度 | 现状 |
|---|---|
| 后端 | Django 6 + Wagtail 8，12 个应用，约 7.3 万行业务 Python，37 个自有模型 + 约 30 张第三方表，85 个迁移 |
| 路由 | 前台 72 条 + 后台 /admin/ 100 条 + allauth 14 条 + 工具若干（全量枚举见 `02-routes.md`） |
| 业务规则 | 237 条离散规则逐条盘出（`05-business-rules.md`）——重写的对等契约 |
| 基础设施 | 单 SQLite（WAL + IMMEDIATE）+ 单 worker（30 秒节拍）+ Caddy + 宿主 cron；预渲染静态页 + slots 登录态补齐；邮件队列（20s 超时、1/5/30 分钟重试、待发信人工确认、RFC 8058 退订、34 种信）；AI 增量巡查；备份（在线快照 + Fernet + R2） |
| 前端 | 22 个共享组件、`c-*`/`l-*` 体系（input.css 5957 行，色板关闭、语义色唯一通道）、12 个 JS 文件；CSP 极严（script-src 仅 'self'、零内联）、首页 gzip ≤ 300KB、深浅色三态 + 减动效全站尊重 |
| 认证 | allauth 全套，Argon2 PHC 哈希（**Go 可直接验证，密码无需重置**），按访客 IP 限流数字一整套 |
| 质量纪律 | 约 1750 条测试、299 个守卫经变异验证、浏览器三身份全站遍历、N+1 查询预算、CSP/体积/深浅色钉死测试 |

对重构影响最大的现状事实：

1. 正文已是 Markdown（192 轮）、后台已是自研（196 轮）——Wagtail 真正还提供的只有页面树路由、修订/定时发布、图片库（集合 + renditions + WebP）。这是重写里最重的自建块，但边界清晰。
2. 并发正确性依赖 SQLite IMMEDIATE 写串行（建队/审批/编队都是写事务内二次检查）——Go 侧要等价纪律。
3. 有意设计的「库缺失」语义（删掉的游戏 ID 显示「（游戏 ID 已删除）」、注销用户显示「已注销用户」）靠 SET_NULL/PROTECT 组合实现，新 schema 照搬。
4. 217 复核两条高严重度（/wagtail/login/ 绕过、EXIF 坏队标 500）尚未修。

## 二、目标架构

| 层 | 现在 | 重构后 | 理由 |
|---|---|---|---|
| 前端 | Django 模板 + HTMX + Alpine(CSP) | Vue 3 + TypeScript + Vite | 用户指定；Alpine 实际 0 处使用，HTMX 四类用法都有直接对应物 |
| 样式 | Tailwind CLI + c-*/l-* | 原样保留 | 视觉零变化，design.md 13.2 继续有效 |
| 后端 | Django + Wagtail | Go 单体（chi）+ Go worker | 单二进制、部署简单；chi 是 MIT |
| 数据访问 | Django ORM | sqlc（手写 SQL 代码生成） | 显式查询杜绝懒加载 N+1 |
| 数据库 | SQLite（WAL） | SQLite 继续（mattn/go-sqlite3） | 迁移近乎 1:1，运维故事不变；预留 Postgres |
| 任务队列 | django-tasks-db | 自研 SQLite 任务表（约 500 行） | 语义照搬：on_commit、RUNNING 复位、心跳、去重、优先级 |
| 邮件 | core.mail | go-mail + html/template 同款信纸 | 34 种信逐一对样张验收 |
| 认证 | django-allauth | Go 自研（规格已盘全） | Argon2 PHC 兼容；唯一登录入口，侧门类 bug 从结构上消失 |
| CMS | Wagtail 页面树 | 自建 pages 表 + 修订 + 定时发布 | 4 种页面类型、树深 ≤3 |
| 后台 | backoffice | Vue 后台 | docs/admin.md 就是规格；placed() 变 Go 中间件 |
| 加密 | Fernet | fernet-go 同格式 | 3 个加密列、备份格式不变 |

依赖许可证核过：Vue/Nuxt/Vite/chi/sqlc/go-sqlite3/goldmark/fernet-go/SortableJS 均 MIT，x/crypto、libwebp、imaging 为 BSD，Playwright Apache-2.0——符合硬规则 5。

## 三、开工前要拍板的 8 件事

1. **渲染架构**：A（推荐）Nuxt SSR + 路由级 SWR 缓存，删掉预渲染管线，生产多一个 Node 容器；B 保持现有形态（Vue + SSG 静态公开页 + 登录态水合 API），无 Node 但保留发布触发重建逻辑。
2. **数据库**：SQLite（推荐）还是 PostgreSQL。
3. **cgo**：推荐接受（mattn/sqlite3 + libwebp，WebP 编码无可靠纯 Go 实现）；代价是交叉编译不便（Docker 部署无所谓）。
4. **字体库**（运行时 TTF→fonttools 切片）：Python 边车保留，或首期降级（占位图/图标/校徽/邮件图都是预生成静态文件，只有字体是运行时功能）。
5. **217 两条高**：先在现行 Django 站修掉再启动重写（正式站在跑）。
6. **仓库**：新仓库 sjtu-ow-next（推荐）还是同仓库并行目录。
7. **视觉与 URL**：默认 100% 保持。
8. **范围**：全量对等；字体库、活动数据、/wagtail/ 应急后台、文档库四项可延后。

## 四、迁移策略：干净重写 + 单次割接

不推荐绞杀者：单 SQLite 库不能两套写入栈共享；账号域被所有域引用、通知横切一切，切不出干净的缝；237 条契约已把「漏需求」风险压到最低；低流量社区站停机 1 小时可接受。

保险：staging 用真实备份演练割接剧本 ≥2 次；同一份数据新旧栈各渲染一遍逐页 diff（Playwright）；旧栈只读保留 ≥2 周回滚；重写期间 Django 站功能冻结、只修 bug。

## 五、分阶段计划（11 个里程碑，总量约 150–200 轮 ≈ 1.5–3 个月 + 加固期 30–50 轮）

| 阶段 | 内容 | 完成标准 | 估量 |
|---|---|---|---|
| M0 脚手架 | 新仓库、双语言 CI、Compose 开发环境、令牌与 c-*/l-* 移植、基础布局 | /_styleguide/ 像素级还原；CI 绿 | ~5 轮 |
| M1 Go 基座 | chi+sqlc+迁移+会话+Argon2+限流+healthz+错误页+CSP 中间件+配置 | healthz 四项等价；限流数字钉死；SQLite 写串行有测试 | ~8 轮 |
| M2 认证与账号 | 注册/验证码/登录/改密/重置/改邮箱/注销匿名化/导出/组/can_use | 账号域 42 条契约打钩；Playwright 新人第一晚 | ~12 轮 |
| M3 内容域 | pages 表+修订+定时发布、文章/分类、goldmark 移植全部 Markdown 规则、图片库、搜索 | Markdown 黄金用例逐字节对拍；图片管线同规格 | ~18 轮 |
| M4 前台公开页 | 全部公开页 + 深浅色 + 减动效 + 右键菜单 + 加载条 | 对拍截图通过；CSP 与体积测试通过 | ~15 轮 |
| M5 个人中心 + 战队 | /me/ 全部、自动保存协议、战队全部规则 | 战队域 26 条打钩；自动保存各场景验证 | ~12 轮 |
| M6 赛事 + 内战 | 报名状态机、临时队/散人池/编队、分队算法、Vue 拖拽板 | 赛事 35 + 内战 27 条打钩；算法结果等价；干部流程走通 | ~20 轮 |
| M7 通知+队列+邮件 | 任务表、邮件管线、待发信人工确认、群发 Broadcast、34 种信+样张页 | 逐封信对拍；worker 语义等价 | ~15 轮 |
| M8 AI 审核 + 后台全量 | 巡查全语义、backoffice 八大类 + 门禁中间件 + 待办 + 操作记录 | 后台 100 条路由逐条过门；AI 域 22 条打钩 | ~18 轮 |
| M9 运维 | 备份/恢复、cron 收进 worker、compose 生产栈、监控、错误页 | 测试机完整备份→恢复演练；割接剧本成形 | ~10 轮 |
| M10 数据迁移 | 只读导入器、对账工具 | 真实备份导入 staging 两次全绿 | ~10 轮 |
| M11 割接 | 公告→维护页→备份→导入→新栈→开站；观察 2 周 | 新站健康、回滚在手 | ~5 轮 |

M4 后随时可起「只读新站」对拍；M8 后全功能 staging。

## 六、数据迁移要点

Argon2 PHC 原样搬（m=102400,t=2,p=8），会话全失效重新登录（公告）；三个 Fernet 列解密重加密（兼容历史明文）；软硬删混合按 ON_DELETION 表保序；导入器幂等；django_cache/任务表丢弃。割接前排空邮件队列和待发信。详见 `04-data-dictionary.md`。

## 七、测试与质量策略

237 条契约每条至少一个测试 + 自制变异脚本（改坏守卫跑测试）；移植三件守卫（全路由乱填、后台每地址过门、设计数字钉死）；查询计数包装 + 每页查询预算；journey.py 三模式 → Playwright；CSP 红线不放松（Vue runtime-only、零内联）；首页体积预算重新核定（Vue 运行时 gzip 约 +35KB）。

## 八、放弃与自然消失的东西

没了：/wagtail/ 应急后台、wagtail documents/forms、.po 补翻译、/wagtail/login/ 类侧门问题空间。降级后补：测试厚度（第一版约旧站 40–60%，按认证→状态机→权限门优先恢复）。换法实现：预渲染（按决策 A/B）、check --deploy（govulncheck + 安全头测试替代）、字体切片（边车或延后）。不做：GraphQL、微服务。

## 九、主要风险与对策

1. 漏规则（最大）→ 契约逐条打钩 + 真实数据对拍 + 割接前对新栈再跑一轮 210/217 式全站复核。
2. Markdown 渲染差异（goldmark vs markdown-it）→ 先移植旧测试集做黄金用例逐字节对拍。
3. SQLite 写并发 → 写连接 MaxOpenConns(1) + busy_timeout，M1 定死并有测试。
4. 时区（服务器 Berlin、显示 Beijing、存储 UTC）→ Go 全显式 time.Location。
5. 双栈期间生产站演进 → Django 端功能冻结。
6. 工期失控 → M4/M8 两个可上线检查点；四项延后项随时可砍。

## 建议第一步

拍板 8 个决策项 → 先在现行 Django 站修 217 两条高（割接前最小修复集见 `11-open-issues.md` ④C）→ M0 开工。
