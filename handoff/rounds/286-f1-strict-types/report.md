# 286 实现报告

## 结论

全Web TS/Vue严格类型门已接入pnpm test；正向用例及四类非法类型探针、三处安全/投影变异、Go/Web整组、真实账号35/评论23、桩浏览器与10行四组合对拍通过。修复裸User序列化密码哈希及实际契约读取错误。既有待重写any和各页面行为/视觉债务保留，不把类型绿称迁移完成。

## 实现与范围

1. web/tsconfig.json覆盖site、packages/API/UI/shared、TS配置和测试；strict、strictTemplates、noEmit，不用skipLibCheck或业务目录排除。workspace paths与现有导出一致，避免symlink产生重复诊断；标准HTML data-*声明和Vue dataAttributes配置仅覆盖标准属性。未知Vue属性仍被探针拒绝。
2. 根pnpm typecheck为vue-tsc --noEmit，pnpm test先执行类型门；既有测试机整组及CI都执行pnpm test，因此不另写一套CI。依赖vue-tsc3.3.12 MIT、TypeScript6.0.3 Apache-2.0、@types/node24.19.2 MIT；266已经批准vue-tsc及必要开发依赖，本轮核对发行元数据。未改pnpm安全策略或引入发布时间豁免。
3. 最新TypeScript7.0.2无法供vue-tsc3.3.13加载lib/tsc，属于工具启动失败；换6.0.3。3.3.13及其language-core未满24小时，被既有安装保护拒绝；选10月2日发布的3.3.12，从main原锁增量更新，其他现有包版本保持，peer解析随TypeScript/Node开发类型改变。
4. apigen将具名查询interface展开到普通query记录传给Requester，保留严格键集合而不加宽索引签名；不手改生成文件。正向合法query与非法键探针验证生成契约。
5. 修PageData/dynamic loader的any逃逸、Vue兼容导出多默认声明、布尔ARIA/缺省variant、DOM事件与anchor类型、可空首页/目录/资讯集合。未知标题有明确默认值，稀疏集合先过滤null；新增运行时SSR回归。
6. EmailChange误用CField的help属性，帮助文字此前不在可见帮助区域；改正确slot，SSR验证正文及无未知help属性。
7. 后台现有页面误读articles/entries/avatars/todo等不存在的键，或把报名嵌套数据当平面对象。按真实DTO读取集合、用户大小写字段/外层roles、文章body_md/live/go_live_at、手册步骤、内战和赛事编排结构、巡查/日志字段。待办按服务提供items显示，移除不存在的计数/worker状态。未做独立SPA、编辑器、拖拽或各页完整写旅程，F8/F9状态不变。
8. 设置按真实from_address/smtp_security/moderation字段读写，保留SSL/STARTTLS/明文值；保存只发改动字段，空密码/密钥不覆盖原值，未成功加载不允许提交。新增工具都仅开发依赖，不进入前台包。
9. 类型诊断发现UserDetail返回裸User，PasswordHash会进JSON；标json:"-"，保持其他已有字段兼容。JSON及实际HTTP回归验证不输出哈希；后台用户列表加实际roles，评论加实际article_slug，战队加实际is_recruiting，兼容添加并只经apigen生成契约，避免错误地拿解散状态代替招募状态。三处业务变异抓住密码哈希、slug和roles错误，招募标记有现有真实查询回归。
10. 评论旅程的429假设遇到分钟边界失败，临时库证明首贴08:55:59、后续08:56，拒绝稿实为合法成功写入；驱动改短真实UI burst等实际429，逐个核对成功写入及拒绝留稿，墓碑计数由实际成功数导出，不改业务限流或删桶。

## 实际验收

全部测试机后台，日志/srv/sjtu-ow-check/runs，本机/tmp/sjtuow-286-*.log，未本机兜底。初版诊断含243条（包含symlink重复及合法data-*配置问题），没有称243个独立业务缺陷；中间类型检查失败如实保留日志，不作为通过。

- types-six：工具启动后取得真实源码错误；类型修正过程中生成器期望、发布保护、模板引号等曾失败，逐项修复。
- 20261011-165002-1754239：类型正/负探针与整组首次通过（Web15+211、预算96779），退出0；之后补实际帮助文字回归及真实旅程，按最终记录收口。
- 20261011-165330-cea5a38：三变异/类型探针、整组（Web15+212）及真实账号35过，评论429驱动因分钟边界失败，退出1；之后浏览器/对拍未执行。
- 20261011-165938-bfa53d5：最终串行退出0。Go格式/vet/staticcheck/govulncheck/全部测试/apigen一致；全范围类型门、Web15+212、生产构建、预算96779字节；三处安全/投影变异、正向+四类非法类型探针、真实账号35、真实评论23、桩评论浏览器23/23、BROWSER-CHECK-OK、对拍10/10均通过。对拍max0.153032%，原始parity.json/md，摘录checks.txt。
- 20261011-170624-0416217：补实际HTTP哈希输出回归及最终全范围typecheck，退出0。源代码未再改变运行行为。

## 限制

类型门检查现有全部源码，不代表既有待重写页面中的any已清空；源码守卫清单只缩不涨（AdminHome移出），其余F5–F9随重写消债。本轮10行是受影响正常态对拍，未重复285账号98行或新增错误/限流态截图；账号错误态和F4全身份、真实图片样张、全站旅程、WebKit与试用仍待。后台本轮修数据绑定，不称后台页面完整验收。自查不是独立复核；没有旧站或部署变更。

## 文件

web类型配置/环境声明/依赖锁、API查询生成器与gen、UI/页面数据类型及相关回归；必要Go安全/兼容投影与测试；变异/类型探针、评论真实驱动、规格/验收/许可证说明、STATUS。
