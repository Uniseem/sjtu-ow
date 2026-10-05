# 200 邮件换成站点的样子：交大红为主、山脊页头、原文链接（报告）

## 做了什么

用户 10-05：「邮件发送的模板不好看，现在上面那个配色一股 AI 味，请采用 SVG 风格，就是我们站点的风格，且以交大红为主色」；按钮下那行地址「改成原文链接，且带复制按钮的那种」。

1. **设计**（先改，v7.4）：10.3「HTML 版」重写成页头、图怎么进信、正文、原文链接四条；样张页一条；附录 D
2. **页头**（`templates/email/layout.html`）：交大红 `#9b3a33` 底，左边站点标志（白色圆角方块、红色折角），右边白字「交大守望先锋」、浅红「上海交通大学守望先锋社区」；下面一条是站点的两道山脊（远的半透明白、近的白色），接上白色卡片。卡片去掉 1px 细边，16px 圆角；页脚的网址改成红字
3. **图**（`core/email_art.py` 新，`render_email_art` 命令新，`static/img/email/mark.png`、`horizon.png`）：Pillow 照站点的数字画——标志用 `core.icons.draw`（加了 `fill`、`ink` 两个参数，反过来画），山脊用 `core.placeholders` 地平线的同一条线（同样的种子和高度），按站点地平线 12:1 的比例画成 600×50（存 2 倍大小）。邮箱不显示 SVG，所以是 PNG
4. **图随信走**（`core.mail.LetterMessage`）：信在发出前生成 MIME 时，HTML 那一部分变成 `multipart/related`，带上它引用的 `cid:` 图（`Content-Disposition: inline`）；没引用图的信不带。`letters.message()` 和 `ensure_text_and_html()`（队列里的信、allauth 的信、Wagtail 的通知都走这里）都改用它
5. **正文**：信息表、AI 巡查信的逐条、验证码改成 `#eef0f3` 色块、12px 圆角，行与行之间 2px（逐条 3px）白色切开；按钮是交大红胶囊；验证码数字、链接是红字 `#963830`
6. **原文链接**（`templates/email/parts/button.html`，新过滤器 `readable_url`）：按钮下的地址显示解码后的原文，放进浅灰圆角框，框 `user-select: all`，链接仍是编码过的地址。过滤器只把转义过的非 ASCII 文字转回来（`%2F`、`%3F` 这类不动，不是 UTF-8 的字节原样留着）。纯文本版照旧是编码地址
7. **复制按钮没做**：邮箱客户端不运行脚本，按钮没法写剪贴板；能做的是一点就全选
8. **样张页**：`core.email_art.for_browser()` 把 `cid:` 换成 `/static/img/email/…`
9. 网站其他页面「图片要懒加载」的测试把信里的两张图算作首屏（邮箱不认 `loading=`）
10. AGENTS.md：改了画法跑 `render_email_art`

## 测试

- 新文件 `core/tests/test_letter_look.py`，13 条：页头是交大红、有标志和山脊、旧的深色和橙色不在了（4 种信）；不画边、胶囊按钮、信息表色块和白色切口；原文链接显示中文、链接是编码地址、能全选、纯文本照旧；过滤器只转非 ASCII；信里带两张内嵌图（`multipart/alternative` → `multipart/related`）；队列里的信发出时也带；没引用图的信不带；纯文本的信（Wagtail 通知）也有同样的页头；提交的 PNG 和代码画出来的一致；山脊在红底上、远的一道是成片的半透明色、最下一行是白的；标志是网站图标反过来；样张页的图指向 `/static/`
- 改了的旧测试：「信里没有图片」改成「只有那两张 `cid:` 图」；样张页的 HTML 改成和 `for_browser()` 处理过的比

## 命令输出

测试机整组检查（改了懒加载那条测试后重跑）：

```
1832 条测试分成 4 片
分片 1：458 passed in 60.25s (0:01:00)
分片 2：458 passed in 63.27s (0:01:03)
分片 3：458 passed in 64.53s (0:01:04)
分片 4：458 passed in 63.62s (0:01:03)

== 迁移 (07:36:01)
No changes detected

== 生产配置 (07:36:03)
System check identified no issues (0 silenced).

== 错误页和模板一致 (07:36:05)

== Docker 镜像 (07:36:06)
构建成功：ad2cd16bbf09

== 全部通过 (07:36:06)
```

第一次整组检查红了一条（懒加载的测试把信里的图当成网页图片）：

```
E         Left contains 2 more items, first extra item: '/srv/sjtu-ow-check/shards/4/templates/email/layout.html: <img src="cid:ow-mark" width="36" height="36" alt="" style="display:block;width:'
FAILED core/tests/test_images.py::test_pictures_below_the_first_screen_load_lazily
```

变异（测试机，`mutate.py`，17 处、23 次检查）。第一次漏了一处：

```
MISSED one ridge only -> test_the_ridges_sit_on_red_and_run_into_the_white_card
```

去掉远的那道山脊，近的山脊边缘抗锯齿出来的颜色正好是红和白的中间色，测试只看「有没有这个颜色」就过了。改成每一列要有好几个像素深的一片，重跑：

```
mutations: 17 not applying: none
baseline green, 13 tests
caught the night head back -> test_the_head_is_sjtu_red_with_the_site_mark_and_ridges
caught the ridges from elsewhere -> test_the_head_is_sjtu_red_with_the_site_mark_and_ridges
caught the ridges from elsewhere -> test_every_html_is_the_same_letter_in_the_frame
caught the committed ridges out of date -> test_the_committed_pictures_match_what_the_code_draws
caught one ridge only -> test_the_ridges_sit_on_red_and_run_into_the_white_card
caught one ridge only -> test_the_committed_pictures_match_what_the_code_draws
restored and green; missed: none
```

（日志 `/srv/sjtu-ow-check/runs/20261005-153930-68394e5.log`：23 行 `caught`、0 行 `MISSED`。）

截图（测试机，`shot.py`，无头 Chromium 打开样张信，电脑和手机两个宽度），给用户看了「你已被报名参加」的电脑版和「AI 巡查」的手机版。

画山脊时去掉了一行「最后一行涂白」：重画出来的文件哈希不变（`ecd6faf794a3ced8ea2d73f60c6e2e87`），那一行本来就不起作用。

## 部署（正式站）

没有迁移，没有删文件。`deploy_ship.sh 200`（18 个文件，含两张 PNG）：

```
 Image sjtu-ow-web Built 
 Image sjtu-ow-worker Built 
 Container sjtu-ow-worker-1 Started 
全量生成完成：成功 12，失败 0，删除 0；目录占用 276 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

正式站上只读检查（`/root/smoke200.py`：生成一封 SMTP 测试信，不发送，看它的各部分）：

```
top: multipart/alternative
  text/plain None None 529
  text/html None None 4477
  image/png <ow-mark> inline 1513
  image/png <ow-horizon> inline 10903
art files: ['horizon.png', 'mark.png']
head red: True old night head: False
browser: ['/static/img/email/mark.66ce7638da04.png', '/static/img/email/horizon.ecd6faf794a3.png']
```

两张图在 web 和真正发信的 worker 容器里都在，和本机提交的一致（二进制没被部署脚本去 CRLF 弄坏）：

```
ecd6faf794a3ced8ea2d73f60c6e2e87  /app/static/img/email/horizon.png
66ce7638da04fc5227ac1975ad3fbf0e  /app/static/img/email/mark.png
```

## 没做 / 没验证

- **没在真的邮箱客户端里看过**（正式站还没配发信）。截图是浏览器渲染的；Outlook 桌面版不认圆角，会是直角；QQ 邮箱、网易邮箱会不会把内嵌图也列成附件，没验证
- 复制按钮：邮箱里做不了
- 「之前已经发过 N 次」的提示：201 做
