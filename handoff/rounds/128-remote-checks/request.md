# 128 测试和检查放到测试机上跑

## 背景

用户 2026-10-04：「注意了，各种测试检查放到 IP 为 185.99.135.224 的 vps 上进行，你可以搭建完整的工作测试流」。

到 127 为止，每轮的整组检查（ruff、Tailwind、1483 条 pytest、迁移、生产配置、错误页）和变异测试都在开发者自己的 Windows 电脑上跑，一次 5 分多钟，还要设 `PYTHONUTF8=1`、提防 `tailwind runserver` 中途改写 `app.css`。

核对测试机：SSH 密钥能登录（STATUS 里「测试机升级要你的 SSH 密钥」这条不用等了），但机器重装过：Debian 13、8 核 11 GB、没有 Docker、`/srv` 是空的，原来的 `sjtu-ow-test` 部署不在了；跑着 Komari 监控探针，`/opt`、`/root` 下有别的项目的工具链。

## 本轮范围

1. 测试机 `/srv/sjtu-ow-check/`：uv（GitHub 发布页下载、核对 sha256，缓存也放这里）、仓库克隆。不装系统软件包、不装 Docker
2. `scripts/check.sh`：AGENTS.md「常用命令」那组检查，顺序和 CI 一样（不含 `docker build`，每次部署都会构建镜像）；任何 Linux 机器上能跑
3. `scripts/remote-check.sh`（本机）：把工作区连同没提交的改动做成快照传到测试机，跑整组检查或指定命令（`run …`），能 `attach` 接着看
4. `scripts/pytest-shards.sh`：pytest 分片并行，每片一个 git worktree
5. `core/tests/test_check_script.py`：CI 里的每条命令、每个环境变量都要在 `check.sh` 里，两份不会走样
6. `.gitattributes`：`.sh` 在工作区也保持 LF（Git Bash 跑不了 CRLF 的脚本）
7. AGENTS.md（测试机一节重写、常用命令、两条新坑）、README（CI 一节）

## 不做

- 在测试机上部署测试站（要装 Docker，还要另配域名）；演示站每轮照常升级，构建镜像那步就是 `docker build` 的检查
- 改 CI：CI 照旧在 GitHub 上跑

## 验证

真实跑：测试机上整组检查通过（不分片、分 4 片各一次），`run` 跑单个文件，`attach`；变异（改坏 `check.sh` 的命令和环境变量）放到测试机上跑。

## 验收标准

测试机上整组检查全绿；变异全部被抓到；推送 `main`，CI 绿。
