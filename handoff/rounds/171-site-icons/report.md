# 171 网站图标补齐：favicon.ico、主屏幕图标（报告）

## 做了什么

1. `core/icons.py`（新）：照 `favicon.svg` 的数（32 的方框、圆角 9、折线 (8,21.5)–(16,13.5)–(24,21.5)、线宽 3.2、圆头）用 Pillow 放大 8 倍画、再缩小；`files()`、`write()`
2. `render_icons` 命令（新），生成并提交 `static/img/favicon.ico`（16、32、48）、`apple-touch-icon.png`（180，满版）、`icon-192.png`、`icon-512.png`
3. `static/manifest.webmanifest`（新）：站名「上海交通大学守望先锋社区」、短名「交大守望先锋」、两个图标、主题色 `#a4161a`
4. `templates/base.html`：加 `favicon.ico`、`apple-touch-icon`、清单的链接（SVG 那一条保留）
5. `core/views.site_icon` + `core/urls.py`：`/favicon.ico`、`/apple-touch-icon.png` 301 到带哈希的静态文件；这两个名字加进保留的网址片段（078 的守卫会拦）
6. 设计 v6.55（13.2.5「网站图标」）；AGENTS.md：改了画法跑 `render_icons`；二进制文件去 CRLF 的坑
7. `core/tests/test_site_icons.py`（7 条）

生成的图标拼在一起看过（512、180、192 和 ICO 的 48/32/16 放大三倍），和 SVG 一样。

## 部署时踩到的

演示站升级后 `/favicon.ico` 跳到的文件只有 3160 字节，仓库里是 3163。演示站的升级脚本 `/root/deploy_ship.sh` 会给传上去的文件去掉 CRLF（105 起，Windows 打包会带 CRLF），跳过的类型里没有 `.ico`，图标里碰巧有三处 `\r\n`，被删成了坏文件。改了脚本（服务器上，不在仓库里，改前备份 `/root/deploy_ship.sh.bak-171`）：常见二进制扩展名直接跳过，其余用 `grep -I` 判断；重新传图标升级一次：

```
3163
served 3163B
b'\x00\x00\x01\x00\x03\x00'
```

（ICO 文件头，3 张图。）推送以后服务器 `git pull` 拿到的也是仓库里的原文件。

## 命令输出

变异（测试机，9 处，全部被抓到；第一次跑「去掉 16 像素」没抓到，比对测试只按代码里现有的尺寸逐个比，补上比对尺寸清单以后抓到；「折线下移」本来就该由比对测试抓，形状测试读的是仓库里的文件）：

```
baseline green, 4 tests
caught another red -> test_the_committed_files_are_what_the_code_draws
caught another red -> test_each_png_is_the_svg_shape
caught chevron lower -> test_the_committed_files_are_what_the_code_draws
caught iOS icon rounded -> test_each_png_is_the_svg_shape
caught iOS icon rounded -> test_the_committed_files_are_what_the_code_draws
caught no 16px -> test_the_committed_files_are_what_the_code_draws
caught no apple link -> test_pages_point_at_them_and_the_root_addresses_lead_there
caught no manifest link -> test_pages_point_at_them_and_the_root_addresses_lead_there
caught a temporary redirect -> test_pages_point_at_them_and_the_root_addresses_lead_there
caught no root favicon -> test_pages_point_at_them_and_the_root_addresses_lead_there
caught favicon not reserved -> test_every_fixed_top_level_route_is_reserved
restored and green; missed: none
```

整组检查（测试机）：

```
1636 条测试分成 4 片
分片 1：409 passed in 36.35s
分片 2：409 passed in 36.85s
分片 3：409 passed in 43.56s
分片 4：409 passed in 35.60s
== 全部通过 (05:01:10)
```

演示站（公网）：

```
301 https://sjtu.ow-shanghaiuniversity.com/static/img/favicon.3c4d74971d35.ico -> 200 image/vnd.microsoft.icon
301 https://sjtu.ow-shanghaiuniversity.com/static/img/apple-touch-icon.f1c136bd04a1.png -> 200 image/png 1969B
<link rel="icon" href="/static/img/favicon.3c4d74971d35.ico" sizes="48x48">
<link rel="icon" href="/static/img/favicon.ba14cd1a9eee.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/static/img/apple-touch-icon.f1c136bd04a1.png">
<link rel="manifest" href="/static/manifest.500fcac443d5.webmanifest">
```

## 没做 / 未验证

- 没在真 iPhone、安卓上「添加到主屏幕」看过
- 后台（Wagtail）的标签页图标没动，仍是 SVG
