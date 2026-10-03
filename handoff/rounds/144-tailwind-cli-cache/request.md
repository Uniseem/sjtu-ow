# 144 Tailwind 命令行不再每次重新下载

## 背景

143 跑整组检查时，前两次分别在 Tailwind 那一步和 Docker 镜像那一步失败：下载 Tailwind 命令行时 GitHub 返回 503。查下来，django-tailwind-cli 的 `manage.py tailwind download_cli` 是**强制**重新下载（`ensure_cli_binary(force_download=True)`），文件 112 MB：

- `scripts/check.sh`（照 CI 写的）每次都调它，输出被丢掉了，之前看到的「已经存在」是 `tailwind build` 打的；测试机上那个文件的修改时间就是上一次检查的时间
- Dockerfile 在 `COPY . .` 之后调它，`.dockerignore` 又排除了这个目录，所以每次部署、每次检查构建镜像都重新下载

GitHub 一抽风，检查和部署（演示站和以后的正式站）都会失败。

## 本轮范围

1. `deploy/fetch_tailwind_cli.py`：只用标准库，按版本和架构下载到 django-tailwind-cli 认的文件名，失败重试 5 次，先写临时文件再改名、加执行权限
2. Dockerfile：在 `COPY . .` 之前 `ARG TAILWIND_CLI_VERSION=2.9.0` + 运行这个脚本（这一层能缓存），去掉 `download_cli`；之后的 `tailwind build` 找到文件就不下载
3. `scripts/check.sh`：文件不在时才 `download_cli`（CI 里那条命令照旧出现，和 CI 的对照测试不受影响）
4. AGENTS.md 记一条坑

## 不做

- 改 CI：GitHub 上每次都是新机器，本来就要下载

## 验证

测试：Dockerfile 的版本和设置一致；Dockerfile 里没有 `download_cli`，下载在 `COPY . .` 之前；`check.sh` 有判断；文件名和下载地址和 django-tailwind-cli 自己算的一样（Linux 上）；各架构的名字；失败两次后第三次成功；一直失败时报错且不留半截文件。变异逐条改坏。真实构建一次，再构建时这一层是 CACHED。

## 验收标准

测试机上整组检查全绿；变异全部被抓到；推送 `main`，CI 绿；演示站升级。
