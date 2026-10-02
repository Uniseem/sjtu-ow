# 090 实现报告

## 结论

完成。文章和赛事没有封面时，卡片、头图、横幅、首页大图卡都用本站画的占位图（36 张，九种场景），同一对象永远是同一张。

## 逐条结果

1. **设计 v4.1**（先改文档）：13.2 约束后补「v4.1」一段：占位图是封面位置上的插图，「不要渐变光斑」「不画装饰图案」管的是界面本身。改了 13.2.1 第 1 条、13.2.5 的表和新的「占位图」一节（画法、取图规则、文件、安全、分享图不用、首屏和队标不变）、13.2.6 `c-stage`、13.2.8、5.2 文章页「封面（有才显示）」，附录 D 加 v4.1，文档头版本改 v4.1 / 2026-10-02
2. **生成器** `core/placeholders.py`：纯 Python 拼 SVG，`random.Random(固定种子)`，数字统一保留一位小数，所以输出逐字可复现。九种场景：
   - 用户看过的三种：山峦（中点位移的山脊加柔光）、夜景（三排楼、亮着的窗）、几何（半透明三角和圆）
   - 新加的六种：海面（浪带、太阳和水面反光）、沙丘（平滑曲线、迎光面渐变）、极光（星星、两条光带、山影）、舞台（顶上射下的光束、舞台灯线、观众剪影）、星球（带环的行星、卫星、星空）、松林（三层叠起的松树、晨雾）
   - 每种四套配色，按「配色轮次 × 场景」交错排成 36 张，相邻编号场景不同
   - 一张 2–19KB，36 张共 388KB；WhiteNoise 会再预压缩
   - 第一版的舞台观众太小、松林像草，截图看过后放大了观众、松树改成三层
3. **命令** `manage.py render_placeholders`：写 `static/img/placeholders/cover-01.svg` … `cover-36.svg`，删掉目录里不在清单上的 `cover-*.svg`，别的文件不碰
4. **取图规则** `pick()`：`(ID + 偏移) mod 36`，文章偏移 0、赛事偏移 13；没保存的对象（后台预览新文章）按 0 算。模板过滤器 `{{ obj|cover_placeholder }}`（`core/templatetags/ow.py`）给出静态地址
5. **模板**：`components/post_card.html`、`components/tournament_card.html`、首页大图卡、赛事详情横幅（不再加 `c-stage--plain`）、文章页头图。都写了宽高，卡片 `loading="lazy"`。有封面时走原来的 Wagtail 缩略图
6. **样张页**：两处灰块示例换成占位图；最下面加「占位图」一节，列出全部 36 张和场景名。`input.css` 删掉 `c-media__none`
7. **文档**：README「视觉风格与首页」加占位图一条和命令，原来那句「没有图时用一块灰底」改掉；AGENTS.md 常用命令下补一句（和错误页同样的写法）
8. **测试** `core/tests/test_cover_placeholders.py`（9 条）：已提交文件和生成器逐字一致；命令写全、删旧、不碰别的；文件只有图形（无脚本、事件属性、`<image>`、`href`、文字、`<style>`、外部 `url()`，小于 40KB）；9 种场景、36 张互不相同、相邻不同；取图稳定、相邻 ID 场景不同、同 ID 文章和赛事不同、预览也能取；没有模板再用 `c-media__none`；文章卡片 / 头图 / 首页资讯、赛事卡片 / 横幅 / 首页大图卡都用对应占位图；有封面的赛事三处都不出现占位图。`content/tests/test_editorial_pages.py` 里原来断言灰块的那条改成断言占位图（两篇无封面文章用的不是同一张）

## 验收输出

整组检查（Windows 本机，`PYTHONUTF8=1`）：

```
All checks passed!
250 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1011 passed in 169.92s (0:02:49)
No changes detected
System check identified no issues (0 silenced).
```

（1011 = 089 的 1002 + 本轮新加 9 条。）

变异（`handoff/rounds/090-cover-placeholders/mutate.py`，先跑基线）：

```
基线：19 passed in 6.45s
抓到  文章卡片不用占位图：1 failed, 1 passed in 1.46s
抓到  赛事卡片不用占位图：1 failed, 2 passed in 1.34s
抓到  首页大图卡不用占位图：1 failed, 2 passed in 1.54s
抓到  赛事横幅退回素色条：1 failed, 2 passed in 1.43s
抓到  赛事横幅不放占位图：1 failed, 2 passed in 1.37s
抓到  文章头图不用占位图：1 failed, 1 passed in 1.12s
抓到  有封面也用占位图（文章卡片）：1 failed, 1 passed in 1.12s
抓到  有封面也用占位图（赛事）：1 failed, 3 passed in 1.50s
抓到  赛事和文章不错开：1 failed in 0.73s
抓到  每次随机取，不固定：1 failed in 0.72s
抓到  场景不交错排列：1 failed in 0.69s
抓到  改了画法没重新生成：1 failed, 4 passed in 2.75s
抓到  少一种场景：1 failed, 7 passed in 1.95s
抓到  命令不删旧图：1 failed, 5 passed in 1.71s
抓到  占位图里带脚本：1 failed, 4 passed in 1.60s

15/15 处变异被抓到
改回后：19 passed in 4.05s
```

pytest-django 先跑用数据库的测试，所以「占位图里带脚本」那条可能是被「文件和生成器一致」先抓到的。单独跑安全那条确认它自己也会红：

```
FAILED core/tests/test_cover_placeholders.py::test_the_pictures_are_plain_graphics
1 failed, 8 deselected in 0.29s
```

视觉：本机演示站清掉上一次手动上传的封面后，用无头 Edge 截了资讯列表（12 张卡片 12 种不同的图）、赛事详情横幅、无封面文章页、首页、赛事列表。页面上实际用到的文件（浏览器里取页面数一遍）：

```
"/": "cover-15 cover-13 cover-11 cover-18 cover-22"
"/news/": "cover-22 cover-21 cover-14 cover-20 cover-12 cover-13 cover-19 cover-17 cover-16 cover-11 cover-10 cover-18"
"/tournaments/1/": "cover-15"
"svg": "200 image/svg+xml"
```

首页大图卡和赛事 1 的详情页都是 cover-15，和列表一致。样张页要登录后台账号，本机没有，未截图（模板由 `test_style_guide_opens_for_an_admin_who_is_not_a_superuser` 渲染过）。

## 设计偏差

无。设计先改到 v4.1，实现照它做。

## 未完成 / 顺带发现 / 需要确认

- **和 v4.0 约束的张力**：13.2 约束里有「不要渐变光斑」，占位图里正好有柔光。用户这次是看过图之后要的，我在 v4.1 里把界限写成「管界面，不管图片内容」。用户如果觉得光斑也不该出现在图里，生成器里去掉 `glow()` 就行
- **没加颗粒**：Pillow 版有一层很淡的颗粒，SVG 版没有（SVG 滤镜在手机上每张卡都要重算）。截图里看不出明显差别
- **提交身份**：本机这份仓库是新克隆的，本地没有 `AGENTS.md` 第 9 条说的 `Uniseem` 身份（全局身份是别的）。问过用户后，在仓库本地配置设成 `Uniseem <325086315+Uniseem@users.noreply.github.com>`（和 089 及以前的提交一致）再提交
- 演示数据（用户、战队、文章等）只在本机库里，不进仓库

## 改动文件

- 新增：`core/placeholders.py`、`core/management/commands/render_placeholders.py`、`core/tests/test_cover_placeholders.py`、`static/img/placeholders/cover-01.svg` … `cover-36.svg`、本轮目录
- 修改：`docs/design.md`、`README.md`、`AGENTS.md`、`handoff/STATUS.md`、`assets/css/input.css`、`core/templatetags/ow.py`、`core/styleguide.py`、`core/templates/core/styleguide.html`、`templates/components/post_card.html`、`templates/components/tournament_card.html`、`content/templates/content/home_page.html`、`content/templates/content/article_page.html`、`tournaments/templates/tournaments/detail.html`、`content/tests/test_editorial_pages.py`
