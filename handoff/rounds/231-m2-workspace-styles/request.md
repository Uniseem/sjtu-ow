# 231 M2 第一轮：pnpm 工作区和样式

## 背景

M1（222–230）已经齐了。M2 的完成标准是样张页和旧站并排一致、首页壳在体积预算内（12 号文档 11.2）。这一轮先把前端工作区立起来，并把现行站的 `input.css` 原样搬进 `packages/styles`（6.1、6.5）。后面的 SSR、布局、样张页都站在这上面。

## 本轮范围

### 做

1. `web/` 用 pnpm 工作区（pnpm 11.20.0，和测试机上已有的一致）。`packages/styles`、`packages/api`（230 的生成物留在原地，加一个再导出的入口）。pnpm 11 默认不跑依赖的安装脚本，工作区用 `allowBuilds` 允许 `esbuild` 和 `@parcel/watcher`（Vitest 要用）。
2. `assets/css/input.css` 原样搬到 `web/packages/styles/input.css`。令牌、`@variant dark`、夜带、减动效熔断不动。`@source` 改成扫 `.vue`，不再扫 Django 模板。
3. Tailwind CLI 编出 `dist/site.css`（不提交，和现行站的 `app.css` 一样是产物）。
4. Vitest 守住 6.5 写明要照搬的几条：只留自己的色板、每个颜色都有深色值、`prefers-color-scheme` 只出现一次且在自定义变体里、不加载 daisyUI。编译结果里没有 `bg-orange-500` 的变量、没有 `.btn`。
5. CI 和 `scripts/check.sh` 在 Go 段后面加上 `pnpm install --frozen-lockfile` 和 `pnpm test`。

### 不做

- SSR 服务、路由、布局、样张页（接下来几轮）。
- 接口封装里的 401、待发信、幂等键（6.4）。
- 后台样式包 `admin.css`、错误页 `error.css` 的第二份（错误页仍用现行站那份，等错误页那轮再搬）。
- Vue、Vite、页面组件。
- 正式站。

## 验收标准

测试机上 `pnpm test` 通过；三处变异（色板重置、`prefers-color-scheme` 出现两次、深色块漏一个颜色）先让测试变红再改回。Go 的「CI 只跑新栈」测试仍绿。锁文件提交。依赖只有 Tailwind CLI 和 Vitest，许可证 MIT。
