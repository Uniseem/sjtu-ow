# 271 规定 Claude 和 GPT 各自能改什么

## 背景

270 起前端由 Claude 做、后端由 GPT 做（用户 2026-10-10：「你把前端往下推进，后端之后让 gpt 去写」）。用户接着要求：「规范一下 claude 和 gpt 的各自的可改动范围避免冲突」。

270 只写了一句「前端轮次只改 `web/`，不改 `server/`」，留着几处会撞车的地方：

- 生成的接口代码（`web/packages/api/src/gen/`）在 `web/` 下，却由 Go 生成
- 270 写的是「后端做完一条就删 `pending-api.ts` 里对应的一段」，等于让 GPT 改前端文件
- STATUS 只有一个 `next`，两边每轮都要改同一行；轮次号两边各自取，同时开工会重号
- 266–270 期间 GPT 和 Claude 用的是同一个工作目录：GPT 没提交的草稿（`ServerHtml.vue` 等）留在里面，`remote-check.sh` 会把它一起打包上测试机
- 部署文件、对拍工具、`scripts/check.sh`、CI、各份文档没说归谁

## 本轮范围

只改文档（和 `pending-api.ts` 的头注释）：

1. `AGENTS.md`：把 270 那一句换成「Claude 和 GPT 分开做」：按目录和文件列归属；越界的事怎么交给对方（BE、FE 两张表）；后端改页面在读的字段只许加；同时开工的规矩（各用一个克隆、开工和推送前 `pull --rebase`、`git add` 只写自己的路径、轮次号撞了怎么办、目录名区分前后端）
2. `handoff/STATUS.md`：`next` 拆成 `next_frontend`、`next_backend`；「交给后端（GPT）」加「状态」一栏，交接改成 GPT 标「✓」、Claude 删 `pending-api.ts` 那段后标「已接」；新加「交给前端（Claude）」表
3. `handoff/README.md`：做法表加一行，指向 AGENTS
4. `pending-api.ts` 头注释和新交接方式一致

不做：不建第二个克隆（要用户决定 GPT 在哪个目录干活）；不写自动检查提交范围的脚本。

## 验收

- 测试机整组（`remote-check.sh`）全绿：改了一个 TS 文件的注释
- 自查：AGENTS 的表覆盖仓库每个顶层目录；STATUS、README、`pending-api.ts` 里关于交接的说法和 AGENTS 一致，没有第二份规则
