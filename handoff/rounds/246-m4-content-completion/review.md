# 246 M4 独立复核与自查

## 自查清单

- [x] **设计一致性**：对照 `docs/rewrite-research/12-architecture.md` 5.5、5.12、5.13、5.14、7、8.1 与 `05-business-rules.md` R043–R082、R171–R183、R233 逐条核对。
- [x] **自动保存 v2**：落后 `base_version` 返回 409 stale；30 分钟内同作者覆盖草稿修订，版本号单调自增。
- [x] **权限与生命周期**：普通作者与内容编辑/超管边界清晰；定时上线与到期撤下在后台 worker 轮询中正确翻转 `live` 状态。
- [x] **保留字避让**：保留词命中时追加 `-article`；空时 fallback `article`；冲突自增序号。
- [x] **Markdown 规则**：HTML 原样纯文本；标题降级；本站 figure 外站纯链接；B 站嵌入；字数与阅读时长；目录提取与锚点编号。
- [x] **图片管线**：Master WebP 转换；白名单缩略图限制；物理文件防越界安全。
- [x] **评论与墓碑**：已发布校验；500 字上限；一层扁平化；作者软删除；有回复留墓碑 `[该评论已删除]`；管理员置顶与隐藏。
- [x] **全站搜索**：大小写折叠与子串匹配；关键词上限与长度限制。
- [x] **存量导入**：Django/Wagtail SQLite 存量图片、分类、页面与修订无损导入，严格沿用 ID。
- [x] **新栈编译与测试**：gofmt、go vet、staticcheck、govulncheck、go test 全绿；web/ pnpm test 全绿；测试机 remote-check 验证通过。
