# 079 实现报告

## 结论

**完成。** 文字和底色的每种组合都到了 WCAG 2.1 AA 的 4.5:1，表单控件的边框到了 3:1；原来写死在样式里的 8 处颜色都成了令牌；测试从 `input.css` 读令牌按设计的组合表逐对计算，以后改颜色不达标会红。

## 逐条结果

| 任务 | 结果 |
|---|---|
| 1 设计 13.2.3 | v2.0.2：`ink-3` `#847C7A` → `#726A68`；新增 `control`、`night-ink-3`、`night-line-strong`、`night-control`、`ok-bright`、`warn-bright`、`info-bright`；写明对比度规则和组合表；`line-strong` 的用途改成「装饰性的强线」；13.2.7 表单字段的边框改成 `control` |
| 2 `input.css` | 令牌照改。新增语调变量 `--tone-control`，`.on-night` 里翻到 `night-control`；`.on-night` 的 `--tone-fg-3`、`--tone-line-strong` 改用令牌。输入框 / 下拉 / 文本框（`.c-field` 那一组和 `.c-input`）、复选框和单选、选择块、页头搜索框（原来是发丝线 `line`）、抽屉搜索框的边框改用 `--tone-control`。状态和提示条里 6 处写死的深色状态色改用 `*-bright` |
| 3 `error.css` | `ink-3` 同步，`render_error_pages` 重新生成的维护页只差这一行 |
| 4 测试 | 见下 |
| 5 样张页、截图 | 样张页的色块列表（`core/styleguide.py`）原来也写着 `ink-3` 的旧值、没有新令牌，一起改了，并加了测试：色块要和令牌一一对上 |

原来的 `ink-3` 值正好够做控件边框（白底 4.08、页面底色 3.75），所以 `control` 用的就是它：输入框看起来比原来实一点，页面整体的灰度层次没变。

**改后的对比度**（本轮用测试里同一个公式算的）：

```
ink-3 #726A68        canvas 4.85  surface 5.28  sunken 4.52  red-tint 4.54
control #847C7A      canvas 3.75  surface 4.08  sunken 3.5
night-ink-3 #8F8785  night 5.37   night-2 4.9
night-control #736A69 night 3.59  night-2 3.27
ok/warn/info-bright  night-2 上最低 7.67
```

## 截图

改前改后并排（本会话 scratchpad 的 `shots079/`）：注册页、资讯列表（1280px），个人中心（390px）；样张页看了改后的颜色一节，20 个令牌加 7 个新令牌的色块都有颜色（新的 `bg-*` 类编进了 `app.css`）。输入框和单选的边框从很淡的灰变成清楚的灰；页头搜索框的边原来几乎看不出来，现在有了；资讯列表里日期下的年份、作者名深了一档，和次要文字仍然分得开。没发现别的变化。

## 设计偏差

无。

## 验收输出

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
244 files already formatted

$ uv run python manage.py tailwind build --force
Built production stylesheet '/home/user/sjtu-ow/static/css/app.css'.

$ uv run pytest -q -p no:cacheprovider
958 passed in 243.54s (0:04:03)

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python manage.py render_error_pages
Wrote /home/user/sjtu-ow/deploy/error_pages/maintenance.html
 M deploy/error_pages/maintenance.html     # 只有 --color-ink-3 那一行
```

整组检查跑了两次：第一次 957 passed（那时还没有样张页色块的测试），加了那条测试后又跑一次，上面是第二次的结果。948 → 958。Docker 构建未验证。

## 变异

`handoff/rounds/079-contrast/mutate.py`。第一次跑的时候还没有样张页的测试，前 10 条全部被抓到；加了样张页那条之后再跑一次：

```
KILLED   ink-3 改回 3.75:1 的旧值  | 1 failed, 24 passed in 4.61s
KILLED   控件边框用回 2:1 的浅灰  | 1 failed, 26 passed in 4.75s
KILLED   深色上的控件边框太浅  | 1 failed, 26 passed in 4.69s
KILLED   深色上的第三级文字太暗  | 1 failed, 26 passed in 4.72s
KILLED   深色区块又写死第三级文字  | 1 failed, 28 passed in 4.65s
KILLED   深色区块不翻转控件边框  | 1 failed, 28 passed in 4.78s
KILLED   深色状态色又写死  | 1 failed, 29 passed in 4.72s
KILLED   输入框用回装饰线  | 1 failed, 30 passed in 4.93s
KILLED   复选框用回装饰线  | 1 failed, 31 passed in 4.81s
KILLED   页头搜索框用回发丝线  | 1 failed, 33 passed in 4.98s
KILLED   样张页色块还写旧值  | 1 failed, 27 passed in 5.00s
KILLED   样张页漏掉新令牌  | 1 failed, 27 passed in 5.01s
12/12 killed
```

第一条变异在 `-x` 下先撞上的是已有的「`error.css` 和 `input.css` 令牌一致」那条测试，不一定是新的对比度测试。单独只跑对比度测试再试了一次，它自己也会红：

```
E       AssertionError: assert ['ink-3 on ca...: 3.51 < 4.5'] == []
E         Left contains 4 more items, first extra item: 'ink-3 on canvas: 3.75 < 4.5'
1 failed, 39 deselected in 0.17s
```

## 未完成 / 顺带发现

- **深色页头的搜索框、抽屉里的搜索框**有了 3:1 的边；深色区块里如果以后放普通表单，同样会用上 `night-control`
- `static/css/error.css` 里还有一处 `color: #fff`（维护页的按钮文字），是手写的独立样式表，不在 `@theme` 的规则范围内，没动
- Wagtail 后台的表单不用本站样式表，不在本轮范围

## 改动文件

```
assets/css/input.css                     令牌、--tone-control、控件边框、去掉写死的色值
static/css/error.css                     ink-3
deploy/error_pages/maintenance.html      重新生成
core/styleguide.py                       色块列表
core/tests/test_design_system.py         对比度、只用令牌、控件边框、样张页色块
docs/design.md                           v2.0.2：13.2.3、13.2.7、附录 D
README.md                                视觉风格一节加对比度
handoff/STATUS.md、handoff/rounds/079-contrast/
```
