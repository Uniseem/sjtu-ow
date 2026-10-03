# 112 页头导航在 1280px 左右折行（报告）

## 做了什么

1. **样式**（`assets/css/input.css`，只在 1024px 以上、导航出现的宽度生效）：标志、导航、账号区 `flex-shrink: 0`，导航链接和账号区 `white-space: nowrap`。宽度不够时只有搜索框变窄（它本来就是 `flex: 0 1 36rem`、输入框 `min-width: 0`）。1024px 以下没改，手机上的页头和原来一样
2. **测试**：`core/tests/test_design_system.py` 加 `test_only_the_search_box_gives_way_in_the_masthead`
3. 设计文档没改：13.2.6 本来就没说导航可以折行，这是实现的问题

## 命令输出

修之前，演示站 1280 宽截图：「首/页」「资/讯」「赛/事」「内/战」「战/队」「成/员」「登/录」都折成两行；1180、1024 宽没有搜索框，不折。

修之后，本机（`runserver`，无头 Edge）1024、1280、1366、1440 四个宽度的页头截图都是一行；演示站升级后 1280 宽截图也是一行，搜索框变窄让出位置。

变异（`mutate.py`，3 处）：

```
baseline green, 1 tests
caught the links shrink again -> test_only_the_search_box_gives_way_in_the_masthead
caught nothing keeps its width -> test_only_the_search_box_gives_way_in_the_masthead
caught the links may wrap -> test_only_the_search_box_gives_way_in_the_masthead
restored and green; missed: none
```

整组检查（开发服务器停着）：

```
All checks passed!
276 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
```

```
1289 passed in 158.53s (0:02:38)
```

演示站（镜像时间 `2026-10-03T08:59:34+02:00`）：

```
全量生成完成：成功 46，失败 0，删除 0；目录占用 1604 KB
```

## 没做 / 未验证

- 测试只查样式表里有这几条规则，量不出真实宽度；真实宽度靠上面的截图
- 深色模式、浏览器缩放（比如 125%）下没截图
