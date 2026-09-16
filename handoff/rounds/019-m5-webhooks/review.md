# 019 复核结果

> 实现方自查（用户外出）。等用户回来，008–019 可以一起交给 Grok 做独立复核。

## 结论

**通过。** 自查中发现并修掉 **1 个会让接口文档页完全不可用的问题**，以及 **1 个我自己写的太弱的测试**（正是它放跑了前者）。另外按 018 的教训查了全库，清掉三类前几轮的残留。

自查方式：不看自己写的 `report.md`，拿设计 11.8 的三张表逐条对代码，然后用**真实 HTTP 接收端**和**真实浏览器**跑一遍，而不是只看单元测试绿灯。

## 验证记录

| 验证 | 方法 | 结果 |
|---|---|---|
| 检查与测试 | `ruff`、`pytest`、`makemigrations --check`、生产 `check --deploy` | 421 passed，部署检查干净 |
| 签名互通 | **原样照抄设计 11.8.2 的 `verify_webhook`**，在真实接收端验签 | `signature_valid: True` |
| 篡改检测 | 改请求体、换密钥、用 10 分钟前的时间戳 | 三种都是 `False` |
| 2xx | 接收端返回 200 / 204 | 已送达 |
| 3xx | 接收端 302 到 `/ok` | **没有跟随**：记为失败，`/ok` 没有多收到请求 |
| 超时 | 接收端睡 15 秒 | 10 秒后判失败，无状态码 |
| 重试间隔 | 连续失败到用完 | `[60, 300, 1800, 7200, 21600, 43200, 86400]`，共 8 次 |
| 全部失败 | 第 8 次之后 | 状态 `failed`，超管收到邮件，邮件里有事件 ID |
| 手动重发 | 浏览器点「重发」 | 事件 ID 不变，attempts 归零 |
| 两层过滤 | 订阅了但赛事无关 / 赛事相关但没订阅 / 自己推的本站审核赛事 | 三种都对 |
| payload 冻结 | 发事件后再改报名状态 | 存的 payload 不变 |
| `full` 不含 logs | 真实报文 | `"logs"` 出现 0 次 |
| 联系方式 | 真实报文搜 QQ / 邮箱 | 0 次 |
| 事务回滚 | `transaction.atomic()` 里抛异常 | 一条事件都没发 |
| 地址校验 | http、127.0.0.1、10.0.0.5、169.254.169.254 | 四种都拒绝；投递时会再查一次 |
| 生产开关 | `WEBHOOK_ALLOW_INSECURE_URLS=1` + prod settings | 拒绝启动 |
| 文档页 | 超管 / 非超管 / 匿名，真实浏览器 + curl | 200 / 403 / 403 |
| 清理任务 | 造过期数据后真跑 | 各类删对了，待投递的留着，重复跑幂等 |
| 容器 | `docker build`、`caddy validate` | 都通过 |
| 清理 | **全库计数** | 业务表全 0，只剩骨架 |

## 自查中发现并已修掉

### A1 接口文档页在本站 CSP 下是一片空白（严重）

单元测试断言 `/api/v1/docs/` 返回 200，绿灯。**但在真实浏览器里打开是全白页。**

drf-spectacular 默认的 Swagger UI 模板从 `cdn.jsdelivr.net` 加载 CSS、两个 JS bundle 和 favicon，再用内联 `<script>` 启动。本站的 CSP 是 `script-src 'self'; style-src 'self'; img-src 'self' data:`，于是控制台里 6 条全被拦：

```
Loading the stylesheet 'https://cdn.jsdelivr.net/npm/swagger-ui-dist@latest/swagger-ui.css'
  violates the following Content Security Policy directive: "style-src 'self'"
Loading the script 'https://cdn.jsdelivr.net/npm/swagger-ui-dist@latest/swagger-ui-bundle.js'
  violates ... "script-src 'self'"
Executing inline script violates ... 'script-src 'self''
...
```

而且这**同时违反 README 里自己定的规矩**：「自托管前端脚本（不走 CDN）」，htmx、Alpine、Sortable 都老老实实放在 `static/vendor/`，唯独文档页去了 CDN。

修法两步：

1. 加 `drf-spectacular-sidecar`（官方配套包，把 swagger-ui 的资源装成 Django 静态文件），设 `SWAGGER_UI_DIST: "SIDECAR"` 等三项。现在资源全部来自 `/static/drf_spectacular_sidecar/...`。
2. Swagger UI 自己的启动脚本和样式仍然是内联的，所以给**这一个路径**放宽 CSP，做法照搬已有的 `WagtailAdminCSPMiddleware`：只放 `unsafe-inline`，**不放 `unsafe-eval`，不允许任何外部源**。这页本来就只有超管能看。

修完在真实浏览器里截图确认：页面完整渲染，11 个接口都在，网络请求全部指向 `127.0.0.1/static/...`。

### A2 我的测试太弱，正是它放跑了 A1

第一版：

```python
docs = client.get("/api/v1/docs/")
assert docs.status_code == 200
```

一个从 CDN 取资源、在用户那儿全白的页面，也会返回 200。**断言状态码等于断言「服务端没崩」，不等于断言「这页能用」。**

已经改成断言页面里不出现任何 CDN 域名、并且确实引用了本站的 sidecar 路径，另外加了一条测试确认 CSP 只对这一个路径放宽、首页不受影响。

记一条给自己：**页面类的功能，状态码 200 不算验证过。要么断言正文里的关键内容，要么去真实浏览器里看一眼。**（018 的 A5 是「断言跟着实现走」，这次是「断言太浅」，两次都是测试本身的问题。）

### A3 地址校验有两份实现

字体下载器（008/009）里有一份 `_assert_public_url`，我本来准备在 webhook 里再写一份几乎一样的。两份各写各的，早晚会分叉——比如哪天给一份加了 `is_unspecified`（`0.0.0.0`）而另一份忘了。

抽到 `core/net.py` 的 `assert_public_https_url()`，两边共用，顺手补上了 `is_unspecified`。字体的 79 个测试全过。

### A4 前几轮的残留（按 018 的教训查全库）

018 的 review 里写了「以后每轮清理后应该查一次全库计数」。这次照做了，又查出三类：

- `wagtailembeds.Embed` 1 条 —— 007 轮 B 站嵌入验收留下的
- `core.PrerenderedPage` 11 条 + `prerendered/` 下的静态文件 —— 010 轮留下的，其中 3 条指向 018 已经删掉的文章页

都清了。这条纪律是有用的，继续保持。

## 建议修（转 M6 / M7 或等用户定）

1. **`manage.py backup` 还不存在**（M7）。设计 16.5 要求每天 03:00 备份，现在 `deploy/crontab.example` 里只能注释掉。所有定时任务里这条最不该缺，M7 优先做。
2. **24 小时那档重试没有真实验证过**。验收只确认了 `next_attempt_at` 的计算和任务的返回值，没有真的等 24 小时看 worker 会不会醒。加了 `deliver_due_webhooks` 兜底扫描，但**它现在没有接到 cron 上**——建议 M7 把它排进每天的定时任务，否则兜底本身也不会被触发。这是本轮最实在的一个缺口。
3. **投递失败邮件没有做节流**。一个上游的接收端挂了一整天，每条事件用完 8 次之后都会给每个超管发一封。设计没提，但值得加个合并。

## 认可的判断

1. payload 在事件产生时冻结（设计 12.10.3 明写），重试发的和第一次一模一样——用「发完事件再改状态，然后看存的 payload」验证过。
2. `full` 模式显式剔除 `logs`，而不是指望调用方不给这个展开项。
3. 投递前后各查一次地址：保存时查一次，**发送时再查一次**（DNS 可能变）。
4. 清理任务不碰 `pending` 的投递记录——正在重试的事件不能被从 worker 脚下抽走。用一条 400 天的待投递记录验证过。
5. 生产设置**硬编码** `WEBHOOK_ALLOW_INSECURE_URLS = False` 并且检测到环境变量就拒绝启动，而不是只靠默认值。一个能关掉 SSRF 防护的开关，默认关是不够的。

## 文档更新

- `docs/design.md` 本轮**没有改动**。
- `README.md` 加了 Webhook、接口文档页、定时清理三节。
- `deploy/crontab.example` 新增。
- `handoff/STATUS.md` 轮次表加 019，M5 标记为已完成。
