# 229 复核结果（自查）

连做的自查（`handoff/README.md`），不能替代独立复核。

## 结论

通过。

## 验证记录

- 工作流里没有 `uv run pytest`、`ruff check`、`manage.py`、`docker build`。有 gofmt、vet、staticcheck、govulncheck、`go test`。
- `check.sh` 和 `remote-check.sh` 同样没有这些现行站命令，也没有 `CHECK_LEGACY`、`CHECK_DOCKER`。测试机整组是 `sh scripts/check.sh`。
- 把 pytest 加回工作流（变异 A）或加回 `check.sh`（变异 B），`TestCIOnlyRunsTheNewStack` 变红，改回后恢复。
- 测试机整组日志 `20261008-183157-1ffbdad`：govulncheck 无漏洞，Go 测试通过，退出码 0。没有 pytest、没有镜像构建。

## 发现的问题（都已当场修掉）

第一稿把现行站检查留在 `check.sh` 里，用 `CHECK_LEGACY=1` 才跑。测试机默认虽然关着，开关还在。按后来的要求整段删掉，测试改成这三份文件里出现现行站命令就红。

## 判断里最没把握的

- **旧的辅助脚本还在仓库里。** `scripts/pytest-shards.sh`、`scripts/journey.py`、`scripts/screens.py` 没删。整组不再调用它们。有人用 `remote-check.sh run` 指定一条现行站命令，机器仍会执行，因为 `run` 是通用的。

## 文档更新

- `handoff/STATUS.md`
- `AGENTS.md`
- `README.md`
