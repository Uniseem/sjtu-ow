# 273 实现报告

## 结论
完成 BE-0、BE-1，自查通过。关于、用户协议、隐私政策三页四组合严格对拍全部通过；正式站未部署。

## 逐条结果
1. 普通页从真实 `content_standardpage` 读取，保留旧 ID、Markdown、发布和未发布变更状态、SEO、首次/最近发布时间；旧普通页没有 `body_plain`，从 HTML 生成。草稿仍返回 404，重复导入不增殖。
2. 内容导入九段的查询、扫描、行迭代、事务、SQL 写入、渲染错误全部向上报告。缺必需表报错，评论/点赞表不存在允许跳过，存在但结构错误报错。修订按 Wagtail content_type 选择文章/普通页，不把其他模型的对象编号当页面编号；非法编号报错。
3. 实测发现新库内置图片集合 ID 与旧库不同，固定 key 唯一约束冲突原来被吞。现在在集合事务里释放固定 key，按旧 ID 导入，缺的内置集合补回；保留图片的集合引用，重复导入仍只有六个集合（五个旧集合加新站队标集合）。
4. 普通页 Store 原来扫描了发布时间却没赋值，已补；API 只加 `seo_title`、`search_description`、`last_published_at`（无日期为 null，非空 RFC 3339）。测试机 apigen 生成并取回契约，前端页面和 pending-api.ts 未改。

## 验收输出
全部在测试机后台执行；本机仅编辑、格式化、取回生成物。

- `20261010-225128-9aa2ca0`：内容回归通过，apigen 成功，退出 0。
- `20261010-225231-af1878b`：Go/Web 整组通过，但随后三页对拍在导入集合时 UNIQUE key 冲突，退出 1；修复集合编号后重跑。
- `20261010-225324-e6ce9f5`：迭代错误回滚回归、六处变异、整组通过，退出 0；该快照尚不含集合编号修复。
- 最终 `20261010-225537-93f0339`：内容回归、六处变异、整组、三页四组合严格对拍串行运行，退出 0。本机原始输出 `/tmp/sjtu-ow-273-fixed.log`，测试机 `/srv/sjtu-ow-check/runs/20261010-225537-93f0339.log`。

```text
ok  github.com/Uniseem/sjtu-ow/server/internal/content 1.034s
MUTATIONS-OK 6
No vulnerabilities found.
Tests 15 passed (15)
Tests 171 passed (171)
BUDGET-OK
== 全部通过 (14:56:24)
通过 visitor /about/
通过 visitor /terms/
通过 visitor /privacy/
PARITY 3/3 通过
```

对拍原始报告与各组合数据见 `parity.md`、`parity.json`。变异先 go vet 确认可编译，再跑真实回归；分别验证错误表名、丢 SEO、丢最近发布时间、吞正文写入失败、吞扫描失败、吞行迭代失败。

## 设计偏差
无用户可见设计变化；图片集合冲突修复属于按原设计保留旧 ID 和固定 key。新站要不要跟：本轮就是新站修复。

## 未完成 / 顺带发现 / 需要确认
BE-2 搜索、BE-3 会话投稿资格下一轮。前端仍需按交接规则删除已实现的 pending-api 段并改用生成类型，本轮不将前台页面进度改成整体完成。未跑 browser-check（未改前端入口/壳），未验普通页以外的页面。导入按段事务，后段失败不会撤销先前已完成的段，命令退出失败并报具体原因。

## 改动文件
- server/internal/content/{import.go,api.go,store.go,m4_full_test.go,import_regression_test.go}
- web/packages/api/src/gen/index.ts（仅 apigen 生成）
- handoff/STATUS.md、本轮目录
