# 271 自查

连做轮次，自查不能替代独立复核。

## 结论

自查通过。

## 换角度核对

1. **覆盖面**：用 `git ls-files` 列出所有被跟踪的顶层条目，逐个对照归属表。第一版漏了 `locale/`、根目录的旧站文件（`Dockerfile`、`manage.py`、`pyproject.toml`、`uv.lock`、`conftest.py`）、`scripts/journey.mjs`、`screens.mjs`、`README.md`、`.env.example` 这类共用文件、调研 00–11，都补进了表。根目录的 `internal/` 没被跟踪，不管
2. **只有一份规则**：交接方式在 STATUS 的两张表的引言、`handoff/README.md`、`pending-api.ts` 头注释里都只是一句话加「见 AGENTS」，没有重复写细节。270 写的「后端做完删 `pending-api.ts`」在 AGENTS、STATUS、`pending-api.ts` 三处都改成了前端删
3. **按 266–270 实际出过的情况推一遍**：GPT 的草稿留在共用目录 → 「不共用工作目录」；GPT 268 提交时 269 的文件在工作区挡住对拍编译 → 同一条；两边每轮都改 `next` → 拆成两行；GPT 269 新加接口时顺手重新生成了 `gen/` → 生成物归后端、只由 apigen 写，前端不手改；Claude 270 发现导入 bug → 写成 BE-0 而不是自己改 Go
4. **会不会卡住正常工作**：前端读不到的字段照样能先写页面（`pending-api.ts`）；后端加字段不用等前端；只有改名、删字段要排队，这本来就是会把页面弄坏的改动

## 没验证的

规则本身没有自动检查，靠两边读 AGENTS 遵守。
