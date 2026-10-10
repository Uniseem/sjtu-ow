# 267 实现报告

## 结论

部分完成。用户在实现中要求「先更新下文档然后 push」，本轮按已实现、已验证的范围提交。F2 尚未完成，业务页面进度不因组件实现而标完成。

## 逐条结果

- 新 UI 部件：CPagehead、PostCard、TeamTile、CTournamentCard、CScrimRow、CTeamLogo、CStartsAt。
- 账号骨架：AuthLayout、AuthWhy、AuthBack、AuthError；个人中心骨架 MeLayout，包括资料不全、待发信和按传入权限显示的导航。
- 默认封面按旧站 36 张图及文章/赛事/内战偏移；六栏目的浅色/深色图片来自旧 helper。owISO 输出上海时区 datetime，跨日输入用于对照。
- 文章/战队卡的 site 文件兼容导出到 UI；页面后续仍须补足作者头像、默认封面、成立时间和赛事队伍大小等投影。
- 35 个新增参考由测试机 Django 真实模板渲染生成，落在 legacy-cards.json；和 266 的 60 个参考一起做 Vue SSR 对照。比较规范序列化差异，保留类名、属性、链接和文案。
- 源码守卫补读旧模板图片 helper 中实际生成的类（c-scene），没有加入待重写豁免。
- 未增加第三方依赖，未动正式站。

## 验收输出

所有编译和测试在测试机后台执行。本机只编辑、读日志和取回生成的参照。

参照生成与针对性测试命令：

```sh
bash scripts/remote-check.sh run bash -c 'uv run python handoff/rounds/267-f2-cards-layouts/legacy_fixtures.py && cd web && pnpm install --frozen-lockfile && pnpm --filter @sjtu-ow/site exec vitest run src/ui.test.ts src/guards.test.ts'
```

- 20261010-202432-383bf68：退出码 1，Wagtail pageurl 拒绝 SimpleNamespace；没有到 Vue 测试。改用未保存的真实 ArticlePage，只有 URL 解析 mock。
- 20261010-202745-0e6a0a6：退出码 1，ArticlePage 初始化查询 ContentType，而隔离环境没有表。传入 content_type_id，避免生成参照时碰数据库。
- 20261010-202816-958b16f：生成 LEGACY-CARD-FIXTURES 35；ui.test.ts 98 条全部通过，guards.test.ts 9 通过/1 失败，总计 107 通过/1 失败，退出码 1。问题是 c-scene 由旧 Python helper 生成，守卫只读了 HTML/CSS。
- 第一条整组链 20261010-202931-6de69ed：Go 整组通过，Web 根目录 15 条通过，site 152 通过/1 失败；同一个 c-scene 守卫问题，退出码 1，后续构建和 browser-check 没运行。先把动态主题类改成明确的两种类，再将旧 helper 纳入守卫依据。

最终提交前整组与 browser-check：

```sh
bash scripts/remote-check.sh run bash -c 'sh scripts/check.sh && cd web/apps/site && node browser-check.mjs /usr/bin/chromium'
```

日志 20261010-203046-705e3bd，退出码 0。Go 的 gofmt、go vet、staticcheck、govulncheck、go test 全部通过，No vulnerabilities found；Web 根目录 15 条、site 153 条全部通过，生产客户端与 SSR 构建成功。首页壳 gzip 93166 字节，BUDGET-OK；BROWSER-CHECK-OK。

显示规则变异：

```sh
bash scripts/remote-check.sh run uv run python handoff/rounds/267-f2-cards-layouts/mutate.py
```

日志 20261010-203019-89c6936，退出码 0。13 处全部 CAUGHT（赛事封面偏移、成员夜景、datetime 时区、摘要开关、置顶、战队关闭状态开关、已通过零队、个人队伍文案、取消状态优先、开赛未定、不可用导航、待发信、资料不全），恢复后基线通过：MUTATIONS-OK 13; restored baseline green。

266 推送 CI 已核对：38051587758，Go/Web 均 success。

本轮 git diff --check 退出码 0。

## 未完成 / 顺带发现

- 尚未将新增卡片/布局放进样张；本轮未运行新组件的四种组合截图对拍，也未运行业务旅程。266 的样张证据不能替代这一组验收。
- 真实图片、默认图片池与 API 字段投影尚未逐页验收；AuthError 尚未单独加入旧模板参考。布局只是骨架，不能代表登录、个人中心等页面完成。
- 评论、vue-tsc、自动保存等仍待后续补齐。
- IP 试用站尚未部署。后台旧地址与废弃入口跳转方案已在 266 写入设计；本轮没有实施后台路由迁移。
- 无新增设计决定，沿用 docs/frontend-migration.md、现行模板与设计细节。

## 改动文件

packages/ui 新卡片/布局，shared 图片与日期工具，site 卡片兼容导出/组件对照测试/源码守卫、legacy-cards.json，本轮 request/report/review 与参照/变异脚本、STATUS。
