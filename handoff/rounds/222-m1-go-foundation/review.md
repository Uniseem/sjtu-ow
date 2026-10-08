# 222 复核结果（自查）

连做的自查（`handoff/README.md`），不能替代独立复核。

## 结论

通过。

## 验证记录

- **重跑**：Go 全套（gofmt / vet / staticcheck / govulncheck / test）在测试机上独立跑过三轮（修 goose API、修测试自身的只读池错误、格式化），最终一轮全绿；输出在 report 的「验收输出」
- **变异**（硬规则 7，单点改动、测试机上跑、改完恢复）：
  - `LOCK_EX` → `LOCK_UN`：排队测试红在 `SQLITE_BUSY (5)`——正是 220 轮 E3 实测的那种忙等，flock 的守卫是真的
  - 看门狗拦截条件加 `false &&`：慢事务测试红（`应报 ErrSlowTx，得到 context canceled`）
  - 配置必填检查加 `false &&`：config 包两条红
  - 改完确认文件里已无「变异」字样、整组再跑全绿
- **对照 12 号文档 5.6 逐条**：两池参数（`MaxOpenConns(1)`、`_txlock=immediate`、`busy_timeout(5000)`、WAL、NORMAL、foreign_keys）✓；flock 方案和包注释里「为什么进程内还要互斥量」的推导 ✓；看门狗两阈值和两个模式 ✓；UTC 时间格式（字典序=时间序有测试）✓；「检查—写入同一写事务」由 WriteTx 的形状保证 ✓
- **对照 5.16**：必填三项缺一拒启、生产短密钥拒绝、目录默认值 ✓
- **跨容器**：RESULTS.txt，两容器零 busy 零丢更新，worst_step 190ms 是排队不是忙等

## 发现的问题（都已当场修掉）

1. **WriteTx 提交后才判超时**：初版 fn 慢慢做完、提交成功之后才发现超时，返回错误但数据已落库。改成 fn 返回后先判超时再决定提交
2. npm/pnpm 的 shebang 解析到系统 Node 20（第一次装机栽的），PATH 前置 node24 修掉，坑写进 AGENTS.md
3. `docker run scratch` 是保留名不能直接跑，改用测试机上现成的 caddy:2.10-alpine
4. 查询计数测试把 `ExecContext` 打在只读池上（测试自身的错误），改成写语句包写池
5. goose v3.28 没有 12 号文档写的 `WithEmbedFS`，换 Provider API
6. CI↔check.sh 一致性守卫（128 轮的 `test_every_ci_command_is_in_the_script`）抓到 Go 段两边写法不一致，改成逐条同款——这个守卫干得漂亮

## 判断里最没把握的

- **进程内互斥量没有独立的「拆掉会红」**：只拆互斥量、留着单连接写池，测试照样绿（池本身就是第二道串行）。两层一起拆才会红。按 213 轮的口径记为「有等价兜底」
- **两进程测试的步数余量**：子进程 300 步、父进程 4×200，任何一边慢 1 秒测试也还是绿的（没有时间上限断言）；丢更新和 busy 是硬断言，这个够
- **CI 的 Action SHA**：checkout / setup-go 的 commit SHA 是从 GitHub API 取的（v4 / v6 标签当前指向），没有第二个来源交叉核对
- **govulncheck 的间接漏洞**（import 了但未调用的 2+6 个）：我判断与我们无关（govulncheck 的符号级分析说 0），但没逐个去读那 8 条的详情

## 文档更新

- `AGENTS.md`：「重构进行中」的占位命令换成真的（含工具链位置、npm shebang 的坑）；「常用命令」和 remote-check 段落写死「所有编译和测试一律先在测试机上做」（用户 2026-10-08）
- `scripts/check.sh`、`scripts/remote-check.sh`：Go 段和任务环境
- `.github/workflows/ci.yml`：go 任务
- `handoff/STATUS.md`：本轮一段 + 轮次表一行
