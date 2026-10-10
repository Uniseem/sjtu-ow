# 274 实现报告

## 结论
BE-2、BE-3 完成，自查通过；搜索页四组合严格对拍通过。按用户决定后续由 GLM 接替后端、Claude 继续前端，详细接手指导见 glm-handoff.md。正式站未部署。

## 逐条结果
1. 搜索附加四个固定分组：articles / events / teams / members，空组也在、hits 编码为 []；每组 20 条，第 21 个匹配给 truncated。events 先赛事后内战，合并上限而不是每种各 20。五份既有平铺列表保留，未删除已存在的字段。
2. 查询先去空白截 50 Unicode 字符，最多 5 个词且全部命中。为与 search/services.py 相同，用项目 Python Unicode 15.1.0 生成 298 个 full-casefold 特例，普通字符走 Go unicode.ToLower；未新增依赖。13 个黄金输入直接由冻结旧站 parse_query/excerpt/matches 生成，覆盖汉字、长文本、控制空白、ß、希腊字母、İ、连字、标签与实体、未命中摘录。
3. 读取已保存的正文/说明纯文本。文章按最近发布时间（同值 ID 倒序），赛事/内战/战队按更新倒序，成员按昵称/ID。过滤草稿、取消活动、解散战队、停用/未验证成员；成员只搜昵称，返回原宣言；不搜邮箱、Markdown 原文和链接地址。类别名/活动标签/招募标签与旧站一致。
4. 新迁移 00018 给 pages 添加 search_public，仅用于搜索可见性。文章导入查询本页或祖先的 Wagtail pageviewrestriction，保留发布状态而单独标记受限文章不可公开搜索。回归覆盖本页、祖先、无关分支限制。
5. 搜索查询/扫描/行迭代错误向上报；空查询不读数据库。HTTP 真实注册表+数据库限流器回归证明同 IP 前 30 次 200，第 31 次 429 + Retry-After。
6. SessionUser 增加 can_submit_article，从 BuildViewer 的独立功能限制读出，不与邮箱验证/发表能力混同。六种真实权限组合回归：未验证默认开放、未验证/已验证个人禁用、组禁用、个人允许覆盖组禁用、已验证默认开放。
7. 测试机 apigen 生成并取回；只修改生成 index.ts，未修改前端页面、pending-api.ts 或前台进度表。12 号规格记录应用层 Unicode 匹配与兼容输出。
8. 用户明确 GLM 接替后端，AGENTS 追加原话，后端可改范围与 BE/FE 流程保持。glm-handoff.md（328 行）包含阅读顺序、范围、11 组后端候选任务、核查入口、逐项验收、迁移和运维边界、常见坑、可直接粘贴的启动指令；实时进度仍只写 STATUS。

## 验收输出
全部测试、编译、生成契约在测试机后台执行。

- `20261010-230512-fd8322a`：生成 casefold、旧站 golden，Go search/accounts/content 全部回归，apigen，退出 0。原始输出 `/tmp/sjtu-ow-274-targeted.log`。
- 最终 `20261010-230752-2200302`：15 处变异（每处先 go vet 确认可编译）、Go/Web 整组、搜索四组合严格对拍，串行执行，退出 0。本机 `/tmp/sjtu-ow-274-final.log`；测试机 `/srv/sjtu-ow-check/runs/20261010-230752-2200302.log`。

```text
CASEFOLD Unicode 15.1.0: 298 exceptions
LEGACY-GOLDEN 13
MUTATIONS-OK 15
No vulnerabilities found.
ok github.com/Uniseem/sjtu-ow/server/internal/accounts 16.311s
ok github.com/Uniseem/sjtu-ow/server/internal/content 1.323s
ok github.com/Uniseem/sjtu-ow/server/internal/search 0.300s
Tests 15 passed (15)
Tests 171 passed (171)
BUDGET-OK
== 全部通过 (15:09:04)
通过 visitor /search/?q=%E6%88%AA%E5%9B%BE
PARITY 1/1 通过
```

对拍报告和各组合细节见 parity.md、parity.json。变异覆盖查询 50 字/5 词/全词命中/Unicode、文章公开和发布门、取消活动、文章排序、20 条/截断标记、成员仅搜昵称、会话邮箱混同/忽略禁用、祖先限制导入、HTTP 限流。

## 设计偏差
用户行为保持旧站。原 12 号实现规格用 instr(search_text)，但 SQLite lower 只折 ASCII 且已有索引不等价于 Python full-casefold；按旧站已有应用层扫描设计读取存好的纯文本匹配，并在 12 号 5.14 记录。没有引入分词、FTS 或新依赖。

## 未完成 / 顺带发现 / 需要确认
- BE-0–3 由后端完成不代表全部页面完成；Claude 仍需接生成类型、清理 pending-api.ts 和补旅程。
- search_public 仅用于搜索，未声称新闻列表、详情、首页、sitemap 的受限内容门已验收；GLM 接班优先核查，避免把 live 当 public。
- 首页成员数当前代码只计 is_active，旧设计要求邮箱验证；HomePageOut 未含我的安排、若干首页查询仍吞错。指导列为需回归核查候选，未在本轮扩大修复。
- 迁移前已导入的旧新栈库，search_public 默认 1；本轮验证的是从旧库全新迁移/导入的路径，未提供既有新栈库的限制回填。正式站目前是 Django，未来演练应使用最新快照导入新库；如果保留既有测试站新库要单独核查回填策略。
- 未跑 browser-check（未改前端入口或壳）；未部署试用站或生产站，未访问真实成员库/邮箱。
- 新站要不要跟：本轮就是新栈修复。

## 改动文件
AGENTS.md；12 号文档 5.14；server/db/migrations/00018_search_public.sql；accounts/api.go 与 session_submit_test.go；content/import.go 与导入回归夹具；search/service.go、casefold.go、回归、golden；apigen 的 gen/index.ts；STATUS 和本轮目录。
