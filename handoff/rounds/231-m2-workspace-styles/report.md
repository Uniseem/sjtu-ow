# 231 实现报告

## 结论

完成。`web/` 是 pnpm 工作区，现行站的 `input.css` 原样在 `packages/styles`，四条样式守卫和三处变异在测试机上过了。CI 和整组检查加上了前端这一段。

## 逐条结果

1. 工作区：`web/package.json`、`pnpm-workspace.yaml`、`pnpm-lock.yaml`。包是 `@sjtu-ow/styles` 和 `@sjtu-ow/api`（再导出 230 的生成物）。pnpm 11 不认旧的 `onlyBuiltDependencies`，工作区用 `allowBuilds` 允许 `esbuild` 和 `@parcel/watcher`。
2. `assets/css/input.css` 拷进 `web/packages/styles/input.css`。令牌和深色变体没改。`@source` 改成扫 `apps/**/*.vue` 和 `packages/**/*.vue`。
3. `pnpm test` 先跑 Tailwind CLI，产出 `web/packages/styles/dist/site.css`（gitignore，不提交）。
4. `web/styles.test.mjs` 四条：色板重置还在、编译结果没有 `--color-orange-500`、有 `--color-primary:#9b3a33`、每个颜色都有深色值、`prefers-color-scheme` 只出现一次、没有 daisyUI。
5. `.github/workflows/ci.yml` 加了 `web` 任务；`scripts/check.sh` 有同样的三句（corepack 准备、`pnpm install --frozen-lockfile`、`pnpm test`）。Go 的 `TestCIOnlyRunsTheNewStack` 也要这三句。

## 验收输出

测试机日志 `20261008-185710-cd2dfa7.log`，退出码 0。变异（删掉 `--color-*: initial;`、多写一处 `prefers-color-scheme`、深色块去掉 `--color-toast`）都是 Vitest 变红，改回后 4 条通过：

```
抓到 A 色板重置被拿掉（退出码 1）
抓到 B prefers-color-scheme 出现两次（退出码 1）
抓到 C 深色块漏了 toast（退出码 1）
三处都抓到，已改回
MUTATIONS-OK
```

同一条命令接着 `sh scripts/check.sh`。govulncheck：

```
No vulnerabilities found.
Your code is affected by 0 vulnerabilities.
```

前端段：

```
== Web（新栈） (10:57:38)
Scope: all 3 workspace projects
Already up to date
Done in 267ms using pnpm v11.20.0
...
 Test Files  1 passed (1)
      Tests  4 passed (4)
== 全部通过 (10:57:40)
```

锁文件在测试机 `pnpm install` 之后用 `scp` 拿回来（1599 行，`lockfileVersion: '9.0'`）。Tailwind CLI 4.3.3，Vitest 3.2.7。

## 设计偏差

没有。样式搬迁和守卫是 12 号文档 6.1、6.5。`error.css` 这轮没搬，request 里写了不做。

## 未完成 / 顺带发现 / 需要确认

- 删掉 `--color-*: initial;` 之后，编译结果里仍然没有 `--color-orange-500`（这条断言还是绿的）。变红的是源文件里必须有这行。Tailwind 4.3 不把没人用的默认色写进产物，所以编译断言现在抓不到「重置被删」。等有 `.vue` 用到工具类，再看要不要加一条「用了 `bg-orange-500` 就编不出来」。
- 第一次安装用了 pnpm 10 的 `onlyBuiltDependencies`，pnpm 11.20.0 不读它，`pnpm install` 退出码 1（`ERR_PNPM_IGNORED_BUILDS`）。改成 `allowBuilds` 之后过了。日志 `20261008-185326-c8b61dd`。
- 依赖是这轮新加的：`tailwindcss`、`@tailwindcss/cli`、`vitest`，都是 MIT。12 号文档已经定了用 Tailwind 和 Vitest。
- SSR、路由、布局、样张页还没做。

## 改动文件

- `web/package.json`、`web/pnpm-workspace.yaml`、`web/pnpm-lock.yaml`、`web/vitest.config.js`、`web/styles.test.mjs`
- `web/packages/styles/package.json`、`web/packages/styles/input.css`
- `web/packages/api/package.json`、`web/packages/api/src/index.ts`
- `.github/workflows/ci.yml`、`scripts/check.sh`、`.gitignore`
- `server/internal/platform/config/ci_test.go`
- `AGENTS.md`、`README.md`
- `handoff/rounds/231-m2-workspace-styles/`、`handoff/STATUS.md`
