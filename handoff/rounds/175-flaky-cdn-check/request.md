# 175 两条会随机失败的测试改准

## 背景

174 推送后看 CI 时发现 171 那次是红的（172、173 又绿了，当时没注意到）。失败的是 `scrims/tests/test_teaming.py::test_the_board_carries_what_the_capacity_rule_needs` 的最后一句 `assert "cdn" not in html.lower()`：本意是「拖拽脚本从本站的静态文件加载、不走 CDN」，但它查的是整页有没有「cdn」三个字母。页面里有 CSRF 令牌、内容安全策略的随机串，转成小写后碰巧出现「cdn」就红。`tournaments/tests/test_adhoc_teams.py` 有一模一样的一句。

另外 173 的报告和复核里有一句写错了，按规矩加更正。

## 本轮范围

1. 两句都改成「页面上没有从别的主机加载的 `<script>`、`<link>`」
2. 173 报告、复核里关于「停用时不撤回申请」的说法加「175 轮更正」
3. AGENTS.md 记一句这个坑

## 验证

把两个页面的模板各加一个从 CDN 加载的脚本或样式，测试要红（变异脚本）。

## 验收标准

测试机上整组检查全绿；变异全部被抓到；推送 `main`，CI 绿。
