# 105 复核结果（自查）

## 结论

自查通过。演示站的响应头、缓存、压缩符合设计 v6.3；提前准备下一页在 Chromium 里会触发，至少预取会被用上。

## 验证记录

- **先找原因再改**：206 是在服务器上用同一个 Caddy 镜像对比三种配置定位到 `precompressed` 的；图片缓存、安全头都是从实际响应头看出来的，不是推测
- **两份内容安全策略不会分叉**：Caddyfile 里那份和 `build_policy(settings.SECURE_CSP)` 一字一字比，改任意一边测试都红；`X-Frame-Options`、`Referrer-Policy`、`Cross-Origin-Opener-Policy` 也和 Django 设置比
- **只放开了需要的那一点**：`script-src` 只能是 `'self'` 和 `'inline-speculation-rules'`，页面里除了 `type="speculationrules"` 的 JSON 不能有内联脚本，原有的两条测试照旧守着
- **不会提前打开不该打开的页面**：后台、登录注册（含退出）、个人中心、片段、样张页和下载、新窗口链接都排除，五处变异各自让测试红
- **新鲜度不变**：预渲染页仍然 `max-age=0, must-revalidate`，提前准备的页面也是从服务器现取的；登录状态等页面真正显示才取
- **重跑**：整组检查和变异在提交前跑过，输出在 `report.md`

## 发现的问题

必须修：无。

建议修：`report.md` 两条（测试机同样的问题；没人用的预压缩文件）。

## 判断里最没把握的

1. **`moderate` 的范围**：电脑上停 200ms 就准备，一次最多准备两页（Chromium 的上限），点不点都会多一次请求和渲染。站点页面小、预渲染页由 Caddy 直接返回，服务器压力可以忽略；如果用户觉得流量多，可以换成 `conservative`（按下才准备）
2. **现场压缩代替预压缩**：zstd/gzip 比 brotli 11 级稍大一点（几 KB 的页面差几百字节），换来的是正确的 200 状态码；Caddy 修好后可以把 `precompressed` 加回来（有测试拦着，到时要一起改测试和设计）
3. **完整预渲染没有在真实浏览器里看到**：只能在被调试工具控制的浏览器里测，预渲染被拒、预取成功。按 Chromium 的行为，普通浏览器里会是完整预渲染

## 文档更新

- `docs/design.md`：v6.3（文档头、技术选型表、13.10、13.13.2、13.13.3、15.2、附录 D）
- `README.md`：改 Caddyfile 要重启 proxy；半静态渲染的响应头和提前准备
- `AGENTS.md`：`Caddyfile.vps` 的重新生成、`build -q` 的提醒；CRLF 一条坑
- `handoff/STATUS.md`：头部、现在该谁动手、轮次表加 105
