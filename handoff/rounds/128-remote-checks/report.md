# 128 测试和检查放到测试机上跑（报告）

## 做了什么

1. **测试机**：先按用户说的搭在 `185.99.135.224`（重装过、没有 Docker，跑着别人的探针和工具链）。中途用户把测试机换到 `2a0e:6a80:3:9c7::`（只有 IPv6，4 核 EPYC 9275F、19 GB、有 Docker，整台归本项目），就搬了过去，旧机器上自己建的 `/srv/sjtu-ow-check`（805 MB）删掉
2. 两台都是同一个布局 `/srv/sjtu-ow-check/`：uv 0.12.22（GitHub 发布页下载，`sha256sum -c` 通过）和它的缓存、仓库克隆、分片 worktree、每次检查的日志。不装系统软件包
3. `scripts/check.sh`：AGENTS.md「常用命令」那组，顺序和 CI 一样；`CHECK_SHARDS` 分片，`CHECK_DOCKER=1` 一开始就在后台 `docker build`，最后等它
4. `scripts/remote-check.sh`（本机跑）：
   - 用临时索引把工作区（含没提交的改动）做成提交，打成 bundle 传过去，测试机检出的就是本机现在的样子
   - 检查在服务器上用 `setsid` 脱离连接跑，本机每 3 秒用短连接取一次日志
   - 用法：`run 命令…` 只跑一条命令，`attach` 接着看最近一次
   - 服务器上有锁，同一时间只跑一个
   - IPv6 地址传给 `scp` 时自动加方括号
5. `scripts/pytest-shards.sh`：先收集测试 ID，按顺序轮流分到 N 片（`auto` = 核数）。每片一个 git worktree，各有测试库、`prerendered/`、`.venv`，留着下次用；pytest 用 `@文件` 读 ID，不经过 shell 引号
6. 根目录 `conftest.py`：测试里的密码哈希换成 MD5（网站照旧用 Argon2）
7. `core/tests/test_check_script.py`：CI 的每条命令、每个环境变量都在 `check.sh` 里，`check.sh` 会构建镜像
8. `.gitattributes`：`.sh` 工作区里保持 LF
9. AGENTS.md：测试机一节重写；「常用命令」写怎么在测试机上跑；三条新坑（长连接被掐、测试库是固定文件、测试密码哈希是 MD5）。README 的 CI 一节

## 为什么不是 `ssh host 长命令`

旧测试机上第一次整组跑到 pytest 48% 时连接被断，服务器上的检查跟着被杀：

```
...................................Connection to 185.99.135.224 closed by remote host.
real	5m8.444s
```

服务器日志记的是 `Connection closed by 42.2.114.8`（本机这边断的）。专门试了一次每秒都有输出、开着 `ServerAliveInterval=20` 的连接，1 分 53 秒照样断：

```
105
106
Connection to 185.99.135.224 closed by remote host.
real	1m53.184s
```

所以检查改成在服务器上脱离连接跑。新机器上没观察到断线，但做法照旧。

## 命令输出

旧测试机，不分片（脱离连接以后第一次跑通）：

```
== pytest (19:01:31)
1483 passed in 377.40s (0:06:17)
...
== 全部通过 (19:07:56)
real	6m52.004s
```

旧测试机，按文件分 4 片（第一次建虚拟环境）：

```
分片 1：372 passed in 171.60s (0:02:51)
分片 2：371 passed in 140.04s (0:02:20)
分片 3：371 passed in 154.44s (0:02:34)
分片 4：371 passed in 191.70s (0:03:11)
real	3m48.294s
```

新测试机，按测试轮流分 4 片，还是 Argon2：

```
1485 条测试分成 4 片
分片 1：372 passed in 110.91s (0:01:50)
分片 2：371 passed in 110.73s (0:01:50)
分片 3：371 passed in 104.30s (0:01:44)
分片 4：371 passed in 104.38s (0:01:44)
real	2m31.902s
```

换成 MD5，加上后台 `docker build`：

```
分片 1：372 passed in 41.34s
分片 2：371 passed in 41.11s
分片 3：371 passed in 42.50s
分片 4：371 passed in 40.43s
...
== Docker 镜像 (19:16:30)
构建成功：6df1d3a957aa
== 全部通过 (19:16:30)
real	1m25.743s
```

提交前最后一次整组：

```
1485 条测试分成 4 片
分片 1：372 passed in 32.04s
分片 2：371 passed in 32.31s
分片 3：371 passed in 32.80s
分片 4：371 passed in 31.31s
== 迁移 (19:20:30)
No changes detected
== 生产配置 (19:20:31)
System check identified no issues (0 silenced).
== 错误页和模板一致 (19:20:32)
== Docker 镜像 (19:20:33)
构建成功：9b4d7f4507d9
== 全部通过 (19:20:33)
real	1m8.354s
```

本机原来整组要 5 分多（127：`1483 passed in 320.62s`）。

变异（在测试机上跑，`bash scripts/remote-check.sh run uv run python handoff/rounds/128-remote-checks/mutate.py`，6 处第一次全部被抓到）：

```
baseline green, 2 tests
caught no migration check -> test_every_ci_command_is_in_the_script
caught no error page check -> test_every_ci_command_is_in_the_script
caught no plain pytest -> test_every_ci_command_is_in_the_script
caught no ruff format -> test_every_ci_command_is_in_the_script
caught the deploy check without the redirect -> test_the_script_sets_the_same_environment
caught dev settings not chosen -> test_the_script_sets_the_same_environment
restored and green; missed: none
real	0m32.052s
```

`attach` 接上最近一次，打出完整日志，按它的退出码退出。

## 没做 / 未验证

- 变异脚本本身还是一处一处串行跑；要并行得给每处变异一个 worktree，下次需要时再做
- 测试机上没有部署可以点的测试站（演示站每轮照常升级）
- `remote-check.sh` 的分支（重连、排队等锁）只在真实使用里走过重连以外的路径；排队那条没有专门试
- 本机 `~/.ssh/config` 是这轮新建的（原来没有这个文件，AGENTS.md 说登录信息在那里）
