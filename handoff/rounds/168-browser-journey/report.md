# 168 在真浏览器里走一遍新人的第一晚（报告）

## 做了什么

1. `scripts/journey.py`（新）：见请求。复用 `screens.py` 的种子数据、开发服务器启动方式和 DevTools 连接；`Watching` 记下浏览器自己的消息（`Runtime.exceptionThrown`、`Log.entryAdded` 的 error、`console.error`）；验证码从 worker 打到控制台的邮件里读：按 79 个「-」切开每封信，按邮件解析、解码纯文本部分，再找「验证码：」
2. **修了一处走流程时发现的界面问题**：战队的申请、新建、管理三个页面，整表单的错误显示两遍。共用的表单片段 `account/_form.html` 已经显示 `form.non_field_errors`，这三个模板在上面又写了一遍。删掉三处，加测试
3. AGENTS.md：这个工具；「编号一律过一道关」（166、167）；「用了 `account/_form.html` 就别再自己写 `form.non_field_errors`」
4. `teams/tests/test_form_errors_once.py`（2 条）

## 走的过程

第一版脚本几处没走通，都是脚本自己的问题，网站是对的：

- 游戏 ID 的新增表单在 `/me/game-accounts/?new=1`（页面上是「新增游戏 ID」链接），不在列表页
- 内战报名区写着「暂时不能报名：资料不完整（缺少联系方式）去补全：联系方式」：新人没填联系方式，网站按设计拦下并给了入口。脚本加上「加联系方式」一步
- 「是否来自交大」的值是小写 `true`
- 验证码：第一版在 worker 日志里找 6 位大写字母数字，碰巧找到过；收紧后发现纯文本部分是传输编码过的，日志里没有字面的「验证码：」，HTML 部分全是 `1A2130` 这种 6 位颜色。改成按邮件解析解码
- 战队申请的位置是三个勾选框 `role_tank` / `role_damage` / `role_support`，不是 `roles`。脚本没勾，提交后页面提示「请至少选择一个意向位置。」——**这里看到这句提示出现了两次**，查下来就是上面第 2 条

## 命令输出

`journey.py`（测试机，修完以后）：

```
ok  注册表单提交
ok  验证码邮件发出
ok  验证后到了个人中心
ok  加了游戏 ID
ok  加了联系方式
ok  报了内战
ok  申请了战队
ok  首页「我的安排」里有这场内战
ok  浏览器没有报错
全部走通
```

修之前，用测试客户端提交空的申请表，数这句提示出现几次（临时脚本）：

```
COUNT 2
CTX <span>请至少选择一个意向位置。</span></p>
CTX <span>请至少选择一个意向位置。</span></p>
```

变异（测试机，3 处，全部被抓到）：

```
baseline green, 2 tests
caught apply says it twice again -> test_the_apply_page_says_it_once
caught apply says it twice again -> test_no_page_repeats_what_the_shared_form_says
caught create says it twice again -> test_no_page_repeats_what_the_shared_form_says
caught the shared form stays silent -> test_the_apply_page_says_it_once
restored and green; missed: none
```

整组检查（测试机）：

```
1628 条测试分成 4 片
分片 1：407 passed in 42.41s
分片 2：407 passed in 48.56s
分片 3：407 passed in 41.34s
分片 4：407 passed in 40.13s
== 全部通过 (03:46:52)
```

演示站已升级（模板改动）。

## 没做 / 未验证

- `journey.py` 不进 CI（要 Chromium），改了这几个页面的表单或脚本后手动跑
- 走的是开发服务器，预渲染关着，「登录后替换区块」走的是 Django 直接渲染那条路，没走静态页加 `state.js` 取区块那条路（那条路 13.13.3 的测试覆盖）
