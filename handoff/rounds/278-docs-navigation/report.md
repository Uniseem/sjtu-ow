# 278 实现报告

## 结论

文档职责重组完成，自查通过；测试机文档审计及 Go/Web 整组退出 0。本轮只整理文档，不改网站、依赖、生成契约或服务器。

## 逐条结果

1. AGENTS 从 314 行缩为 36 行：常驻约束、开工顺序、触发读取的任务表。CLAUDE 继续引用同一个入口。
2. README 从 550 行缩为 35 行：项目介绍、人类入口和代码地图；原功能/运行说明保留到 docs/legacy-guide.md，CI 说明转到唯一的开发验收正文，相对链接按新位置调整。
3. docs/README.md 定义按任务导航和事实维护位置。设计主体不拆、不重编号，避免章节引用和守卫漂移；只修正文档移动涉及的导航引用，不变更业务设计版本。
4. 原 AGENTS 的职责表/FE-BE/轮流工作规则移到 handoff/OWNERSHIP.md；命令、工具链、分层、变异和后台检查规则移到 docs/development.md；机器/部署/备份约束移到 operations；踩坑移到 pitfalls。敏感信息限制、依赖审批、部署审批和旧站冻结仍留在入口。
5. STATUS 从 1069 行缩为 177 行；当前前台底座/F2/页面表、BE-0–8、FE-0–4 保留；迁出旧轮次叙述、旧里程碑表、拍板记录和过时上线清单到 handoff/archive/status-through-277.md，原文保留且醒目标记仅为历史。近期摘要最多 3 条。仍需处理的运维事项和未闭环真实环境验收留在当前表。
6. handoff/README.md 维护轮次/署名/提交/交班，指向唯一职责表与验收正文；明确当前 SHA 的 CI 和文档专项轮次命名。长期前端 Claude、后端 GLM 的分工保持，277 范围例外不延长。

## 验收输出

全部在测试机后台执行。首轮 `20261011-020906-a878bff` 退出 1：链接和踩坑通过，范围行比对把「AGENTS 已知的坑 → docs/pitfalls.md」的文档路径移动算成不一致；修正审计的路径对应后重跑，没有放宽范围或删除原条目。首轮未进入 Go/Web 整组。

最终 `20261011-021035-9ea4624`：文档审计后执行 `sh scripts/check.sh`，退出 0，真实摘要：

```text
LOCAL-LINKS-OK: 100 references in 17 documents
PITFALLS-OK: 79 original entries preserved in order
OWNERSHIP-OK: 15 original scope rows preserved
STATUS-OK: 105 current table lines unchanged; historical tail verbatim; recent count 3
LEGACY-GUIDE-OK: all 28 original sections retained; CI redirects to development
DOC-AUDIT-OK
```

Go 格式、vet、staticcheck、govulncheck、测试、apigen 比对全通过。govulncheck 报代码调用漏洞 0（required modules 中另有 3 项未调用，不写成依赖零漏洞）。Web 测试 `15 passed` + `202 passed`，生产客户端/SSR 构建通过，首页壳 gzip 96649 字节、BUDGET-OK。完整摘要见 verification.txt。

仅修改文档，没有新增业务规则，不另造业务测试或跑浏览器/对拍。最终措辞和报告补齐后，`20261011-021222-2d95457` 只跑文档审计与 diff 检查：20 份文件、100 个本地链接和上述保全项目全部通过，退出 0，没有重复整组。CI 按本轮最终提交 SHA 在推送后另行核查。

## 设计偏差

无产品设计变化，未部署。新站要不要跟：这是共享协作文档整理，两栈开发入口共同使用，不需要网站代码跟进。

## 未完成 / 顺带发现

旧 STATUS 的历史存在「协议待定」「演示站待转正」「M2 不要重做」等已被后续轮次推翻的说法，保留在历史而不留作开工任务。旧清单中没找到最终证据的运维验收继续标待核实，未判定已完成。

文档总量不靠删除证据缩减：设计、机器操作和技术经验仍可查询；减少的是每轮必须加载的入口和重复维护。

## 改动文件

AGENTS.md、CLAUDE.md、README.md；docs/README.md、development.md、operations.md、pitfalls.md、legacy-guide.md；handoff/README.md、OWNERSHIP.md、STATUS.md、archive/status-through-277.md、本轮三份文件；design/admin/design-next/12/13 中引用移动位置的少量文字。
