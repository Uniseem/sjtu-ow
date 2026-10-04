# 160 页脚「账号」一栏跟着登录状态（报告）

## 做了什么

1. `templates/slots/footer_account.html`（新）：`<nav id="slot-footer-account" data-slot="footer-account">`，访客「登录、注册」，登录的成员「个人中心、我的报名、我的战队」
2. `templates/base.html`：页脚原来写死的「账号」一栏换成引用这个区块
3. `core/apps.py`：注册 `footer-account`（和页头 `account` 同一种最简单的模板区块）
4. 设计 v6.52（13.2.7 页脚一行）
5. `core/tests/test_footer_account.py`（2 条）

预渲染的页面按访客渲染，所以静态页里是「登录、注册」；登录的人打开静态页时，`state.js` 本来就要为页头的账号区发一次请求，页面上所有 `data-slot` 一起取回，多这一块不多请求。

## 怎么发现的

159 之后用截图工具（146）在手机宽度看「我的报名」底部 157 加的日历订阅，订阅那一块正常；页脚「账号」一栏对已登录的成员也写着「登录」「注册」。

## 命令输出

变异（测试机，5 处，全部被抓到）：

```
baseline green, 2 tests
caught everyone gets the visitor links -> test_members_get_their_own_pages
caught everyone gets the member links -> test_visitors_are_offered_sign_in
caught not swapped in place -> test_members_get_their_own_pages
caught not registered -> test_members_get_their_own_pages
caught footer written out again -> test_visitors_are_offered_sign_in
caught footer written out again -> test_members_get_their_own_pages
restored and green; missed: none
```

整组检查（测试机）：

```
1606 条测试分成 4 片
分片 1：402 passed in 34.59s
分片 2：402 passed in 37.23s
分片 3：401 passed in 34.97s
分片 4：401 passed in 36.35s
== 迁移 (01:34:19)
No changes detected
== 生产配置 (01:34:20)
System check identified no issues (0 silenced).
== 错误页和模板一致 (01:34:21)
== Docker 镜像 (01:34:22)
构建成功：78d52328ed28
== 全部通过 (01:34:22)
```

截图（测试机，375 宽，已登录的成员，「我的报名」页底部）：页脚「账号」一栏是「个人中心、我的报名、我的战队」。

演示站升级后，公网首页（预渲染的静态页）里的这一栏：

```
<nav id="slot-footer-account" data-slot="footer-account" class="c-footer__col font-nav" aria-label="账号"> <h2 class="c-eyebrow">账号</h2> <a href="/accounts/login/">登录</a> <a href="/accounts/signup/">注册</a> </nav>
```

## 没做 / 未验证

- 登录的人打开静态页时，替换前一瞬间看到的仍是「登录、注册」（和页头账号区一样，替换前带 `ow-state-pending`）。没在真浏览器里看替换前后的闪动
