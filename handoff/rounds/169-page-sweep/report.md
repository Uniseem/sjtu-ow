# 169 每个页面都在真浏览器里打开一遍（报告）

## 做了什么

1. `scripts/journey.py pages`：`journey.py routes`（在 Django 里列出项目自己的地址）→ 用 `screens.py` 种子数据里的编号填上 → 访客、成员、站长各打开一遍（后台只用站长），每页等 1.5 秒，记下浏览器的错误、异常、CSP 拦截和页面状态码。`Watching` 多记了每个页面的状态码；405/404/403 页面上浏览器把自己的错误页记成的「Failed to load resource」不算
2. **修了扫出来的一处**：投稿者打开文章编辑页（`/submit/` 跳过去），浏览器报

   ```
   Error connecting controller SyntaxError: Failed to execute 'querySelectorAll' on 'Document': The provided selector is empty.
   ```

   Wagtail 的标题面板把标题和 slug 字段绑在一起（`w-sync` 控制器，`data-w-sync-target-value` 是 slug 字段的选择器）。130 起投稿者的表单没有 slug，Wagtail 把不在表单里的目标滤掉了，却照样挂上控制器、选择器留空。`content/panels.py` 加 `TitlePanel`：没有可同步的字段时不挂 `w-sync`；文章页用它代替 `Page.content_panels`（里面只有标题面板）
3. AGENTS.md：`pages` 模式；这个 Wagtail 的坑
4. `content/tests/test_submitter_editor.py` 加 1 条：投稿者的标题框没有 `w-sync`，内容编辑的还同步到 `#id_slug`

## 扫的过程

第一遍报了 82 处，几乎都是只收 POST 的地址（删除、退出、审批……）返回 405，浏览器显示自己的错误页并记一次加载失败。过滤掉以后剩两处：

```
BAD 访客 200 /_fragments/scrims/1/actions/
    浏览器报告 error: Failed to load resource: the server responded with a status of 404 (Not Found) http://127.0.0.1:46943/favicon.ico
BAD 成员 200 /submit/
    浏览器报告 console: %s ... Error connecting controller SyntaxError: Failed to execute 'querySelectorAll' on 'Document': The provided selector is empty.
```

第一处是页面片段（没有 `<head>`，浏览器去要 `/favicon.ico`），不是给人直接打开的，扫描跳过 `/_fragments/`。第二处就是上面修的。

## 命令输出

修完再扫（测试机）：

```
看了 135 个地址，0 处有问题
全部走通
```

`journey.py`（新人那条路）照样全部走通。

变异（测试机，4 处，全部被抓到）：

```
baseline green, 1 tests
caught Wagtail's own title panel back -> test_the_title_syncs_to_a_slug_only_when_there_is_one
caught editors lose the slug sync too -> test_the_title_syncs_to_a_slug_only_when_there_is_one
caught controller left on -> test_the_title_syncs_to_a_slug_only_when_there_is_one
caught empty selector left on -> test_the_title_syncs_to_a_slug_only_when_there_is_one
restored and green; missed: none
```

整组检查（测试机）：

```
1629 条测试分成 4 片
分片 1：408 passed in 36.49s
分片 2：407 passed in 39.98s
分片 3：407 passed in 42.90s
分片 4：407 passed in 36.66s
== 全部通过 (04:29:02)
```

演示站已升级。

## 没做 / 未验证

- 只是打开页面，没在后台拖拽页上真的拖（页面加载、脚本连接都没报错）
- Wagtail 自己的后台页面只看了首页和页面列表
