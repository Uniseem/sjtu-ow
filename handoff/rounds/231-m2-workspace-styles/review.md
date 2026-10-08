# 231 复核结果（自查）

连做的自查（`handoff/README.md`），不能替代独立复核。

## 结论

通过。

## 验证记录

- 基线 4 条 Vitest 通过，然后三处变异各自变红、改回后再绿。A 打在 `css.includes("--color-*: initial;")`，B 打在 `prefers-color-scheme` 计数，C 打在深色块缺 `toast`。
- 深色编译断言也过了：产物里同时有「跟随系统且不是浅色」和「选了深色」两段，背景是 `#141a24`。说明 Tailwind 4.3 把 `@variant dark` 展成的形状和现行站测试认的是同一种。
- `sh scripts/check.sh` 的 Web 段是 `pnpm install --frozen-lockfile`（Already up to date）再 `pnpm test`。Go 段 govulncheck 无漏洞。日志 `20261008-185710-cd2dfa7.log`，退出码 0。
- 对照 12 号文档 6.1、6.5。`@source` 只改了扫描目标，令牌块没改。

## 发现的问题（都已当场修掉）

- pnpm 11 删了 `onlyBuiltDependencies`。第一次整组因此在安装时退出。工作区改成 `allowBuilds`。
- 变异 A 最初把重置写成 `revert`。Tailwind 直接拒绝编译，测试没跑到。改成删掉那一行，才由「色板重置还在」这条断言变红。

## 判断里最没把握的

- **编译产物里的 `--color-orange-500` 断言，在没有 `.vue` 用到这个类时是空的。** 删掉重置行，这条仍然绿。真正拦住「这行必须在」的是读源文件的那句。等组件开始用工具类，这条编译断言才有机会抓到默认色漏进来。
- **`input.css` 是一份拷贝。** 现行站以后若再改样式，这边不会跟着变。割接前现行站冻结，不再加功能，所以这轮接受两份。

## 文档更新

- `handoff/STATUS.md`
- `AGENTS.md`、`README.md`（检查命令加上前端）
