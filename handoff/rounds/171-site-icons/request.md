# 171 网站图标补齐：favicon.ico、主屏幕图标

## 背景

继续自主推进。169 扫页面时，一个没有 `<head>` 的页面片段让浏览器去要了 `/favicon.ico`，返回 404。查下来全站只有一个 SVG 图标（`static/img/favicon.svg`）：

- 不认 SVG 图标的浏览器和工具（旧版 Safari、一些书签和订阅工具、抓取预览的服务）会直接要 `/favicon.ico`，现在是 404，标签页、书签上没有图标；演示站 `curl /favicon.ico` 是 404
- 没有 `apple-touch-icon`：在 iPhone 上「添加到主屏幕」，图标是网页截图
- 没有网页清单：安卓上「添加到主屏幕」没有名字和图标

社团成员多数用手机，从 QQ、微信里打开。

## 本轮范围

1. `core/icons.py` + `render_icons` 命令：用 Pillow 按 SVG 同样的形状（交大红圆角方块、白色折线）画出 `favicon.ico`（16、32、48）、`apple-touch-icon.png`（180，满版不留圆角，iOS 自己裁圆角）、`icon-192.png`、`icon-512.png`，提交进仓库。不加依赖（Pillow 本来就有，它画不了 SVG，所以照着形状画）
2. `static/manifest.webmanifest`：站名、两个图标、主题色
3. `base.html` 加 `favicon.ico`、`apple-touch-icon`、清单的链接；`/favicon.ico`、`/apple-touch-icon.png` 永久跳转到静态文件，这两个地址加进保留的网址片段
4. 设计 13.2.5（v6.55）；AGENTS.md「改了什么跑什么」加一句

## 验证

测试：图标的尺寸和颜色（四角、底色、折线上的点）；仓库里的文件和代码画出来的一样；页面上有三个链接；两个根地址跳到存在的静态文件。变异逐条改坏。演示站上 `/favicon.ico` 不再 404。

## 验收标准

测试机上整组检查全绿；变异全部被抓到；推送 `main`，CI 绿；演示站升级。
