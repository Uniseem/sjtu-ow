# 108 加载条走满再淡出（报告）

## 做了什么

1. **设计 v6.6**：13.2.4「等待时」加「新页面到了」那一段、「减少动态效果」补一句，13.2.7 `c-loadbar` 一行，附录 D
2. **`static/js/loading.js`**：
   - 点击 150ms 后（`SHOWN_AFTER`，和样式里的延迟一致，有测试比对）才在 `sessionStorage` 的 `ow-loading` 里记一笔 `{at, from: 0}`，所以 150ms 内就到的页面不留记录
   - `pagehide` 时，加载条在走、而且已经记过，就把当前宽度（`transform` 矩阵的横向缩放）写进 `from`
   - 开始新的一次加载时先清旧记录、去掉 `is-arriving`；停止（15 秒、后退回来）时清记录
3. **`static/js/arrival.js`**（新，在 `<head>` 里 `theme.js` 后面同步加载）：读出记录并删掉；20 秒以上的作废；`from` 不在 0 和 1 之间时用 0.6；给 `<html>` 设 `--loadbar-from` 并加 `is-arriving`。被提前准备的页面等 `prerenderingchange` 再读
4. **`assets/css/input.css`**：`.is-arriving .c-loadbar` 两段动画：`ow-loadbar-finish` 300ms `cubic-bezier(0.2, 0, 0, 1)` 从 `scaleX(var(--loadbar-from, 0.6))` 到 `scaleX(1)`，接着 `ow-loadbar-fade` 250ms 淡出。减少动态效果时全局规则把时长压到 0.01ms，条直接消失
5. **`templates/base.html`**：`<head>` 里加 `arrival.js`
6. **测试**：`core/tests/test_transitions.py` 加 4 条
7. **探测脚本**：`finish_probe.py`（真的点击、1500ms 延迟，新页面上每帧记一次加载条的宽度和透明度）
8. **演示站**：升级到 107 + 108，全量生成

## 命令输出

变异（`mutate.py`，14 处）：

```
baseline green, 4 tests
caught the bar does not run to the end -> test_on_the_next_page_the_bar_runs_to_the_end_then_fades
caught the bar runs on linearly -> test_on_the_next_page_the_bar_runs_to_the_end_then_fades
caught the bar fades before it is full -> test_on_the_next_page_the_bar_runs_to_the_end_then_fades
caught the bar starts from nothing -> test_on_the_next_page_the_bar_runs_to_the_end_then_fades
caught arrival.js not in the head -> test_the_next_page_reads_where_the_bar_was_before_its_first_paint
caught the note is kept for later pages -> test_the_next_page_reads_where_the_bar_was_before_its_first_paint
caught old notes are trusted -> test_the_next_page_reads_where_the_bar_was_before_its_first_paint
caught a prepared page reads while prepared -> test_the_next_page_reads_where_the_bar_was_before_its_first_paint
caught the note is written at once -> test_only_a_bar_the_visitor_saw_is_finished
caught the two scripts use different notes -> test_only_a_bar_the_visitor_saw_is_finished
caught the delays drift apart -> test_only_a_bar_the_visitor_saw_is_finished
caught a new load keeps the old note -> test_only_a_bar_the_visitor_saw_is_finished
caught leaving does not note the place -> test_leaving_notes_where_the_bar_got_to
caught leaving notes a bar that never showed -> test_leaving_notes_where_the_bar_got_to
restored and green; missed: none
```

**无头 Edge，本机开发服务器**（从资讯页点第一篇文章，1500ms 延迟；采样每三帧打印一行）：

```
link http://localhost:8000/news/october-schedule/
{"url": "/news/october-schedule/", "note": "{\"at\":1790992075258,\"from\":0.503726}", "from": "0.503726", "arriving": true, "left": null}
  t=   0ms  width=0.504  opacity=1.00
  t=  30ms  width=0.522  opacity=1.00
  t= 133ms  width=0.897  opacity=1.00
  t= 184ms  width=0.955  opacity=1.00
  t= 232ms  width=0.985  opacity=1.00
  t= 283ms  width=0.998  opacity=1.00
  t= 330ms  width=1.000  opacity=0.95
  t= 380ms  width=1.000  opacity=0.56
  t= 430ms  width=1.000  opacity=0.23
  t= 483ms  width=1.000  opacity=0.08
  t= 532ms  width=1.000  opacity=0.01
  t= 584ms  width=1.000  opacity=0.00
  ...
  last: [913, 1, 0]
```

旧页的加载条走到 0.504 时离开、记下；新页面第一帧就从 0.504 开始（不跳），先快后慢地走满（约 300ms），再淡出（约 580ms 时完全消失）；记录读完删掉（`left: null`）。

（第一次跑时采样的时钟从文档创建算起，1500ms 延迟下第一帧在 1573ms，循环只采了一次就停了；改成从第一帧算起。）

**同一个探测跑演示站**：

```
link http://169.58.217.180:22887/news/october-schedule/
{"url": "/news/october-schedule/", "note": "{\"at\":1790992498403,\"from\":0.571453}", "from": "0.571453", "arriving": true, "left": null}
  t=   0ms  width=0.571  opacity=1.00
  t=  57ms  width=0.587  opacity=1.00
  t= 724ms  width=1.000  opacity=0.00
  t= 874ms  width=1.000  opacity=0.00
  last: [904, 1, 0]
```

（演示站上页面还在从网络加载图片，无头浏览器 57ms 到 724ms 之间没出帧，中间没采到；起点和终点和本机一致。）

演示站部署：

```
b01fdf7 107: 缩略图改 WebP、文章正文图片懒加载（设计 v6.5）
 M assets/css/input.css
 M static/js/loading.js
 M templates/base.html
?? deploy/Caddyfile.vps
?? deploy/docker-compose.vps.yml
?? static/js/arrival.js
 Image sjtu-ow-web Built 
 Image sjtu-ow-worker Built 
sjtu-ow-worker 8 seconds ago
sjtu-ow-web 8 seconds ago
 Container sjtu-ow-worker-1 Started 
proxy Up About an hour
web Up 20 seconds (healthy)
worker Up 20 seconds
全量生成完成：成功 46，失败 0，删除 0；目录占用 1595 KB
```

整组检查（开发服务器停着）：

```
All checks passed!
272 files already formatted
No changes detected
System check identified no issues (0 silenced).
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1262 passed in 375.73s (0:06:15)
```

## 发现的问题（不在本轮修）

- 错误页（404、500）不继承 `base.html`，没有 `arrival.js`：点到一个 404 时记录留在 `sessionStorage` 里，下一次加载开始时会清掉，最坏情况是 20 秒内秒开的下一页多一下走满的动画
- 1280px 左右页头导航折行（106 已记）

## 未验证

- 普通浏览器、真实网络下的观感（无头浏览器里验证了起点、曲线、终点和淡出）
- Safari
