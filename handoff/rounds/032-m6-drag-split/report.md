# 032 实现报告

## 结论

**完成。** 按你说的做成了拖拽 + 缓冲区，满员的队伍拖不进去。

## 实际长什么样

角色限定 5v5 的板子：

```
A 队（总分 101）
  ┌ 坦克                      1 / 1 ┐
  │  玩家甲  D0#3200            17  │
  │  坦克 钻石 3 · 支援 宗师 5      │
  │  [A] [B] [缓冲]                │
  └────────────────────────────────┘
  ┌ 输出                      2 / 2 ┐
  │  玩家戊 …  玩家壬 …             │
  └────────────────────────────────┘
  ┌ 支援                      2 / 2 ┐
  └────────────────────────────────┘

B 队（总分 101）  …同上…

┌ 缓冲区（不上场）                0 ┐
└──────────────────────────────────┘
```

**拖进哪个位置区就是分到哪个位置**，不用再单独选一次位置——这是从下拉改成拖拽顺带解决的一件事：原来「换队」和「改位置」是两个控件，现在是一个动作。

## 真实浏览器里的验证

### 满员拒绝

A 队 5 人（满），试着把 B 队的玩家庚移过去：

```
一开始:   {A: 5, B: 5, 缓冲: 0, 总分A: 101, 总分B: 101, 分差: 0}
想把:     玩家庚 移到已满的 A 队
点完之后: {A: 5, B: 5, 缓冲: 0, 总分A: 101, 总分B: 101, 分差: 0}
```

**没动。**

### 你说的那个换人流程

```
1. 把 玩家甲 从 A 队移到缓冲区
   {A: 4, B: 5, 缓冲: 1, 总分A: 84,  总分B: 101, 分差: 17}

2. 把 玩家庚 从 B 队移到 A 队        ← 现在有空位了，进得去
   {A: 5, B: 4, 缓冲: 1, 总分A: 99,  总分B: 86,  分差: 13}

3. 把 玩家甲 从缓冲区补到 B 队
   {A: 5, B: 5, 缓冲: 0, 总分A: 99,  总分B: 103, 分差: 4}
```

每一步总分和分差都实时更新，**一次请求都没发**。

### 保存之后

```
A 队 总分 99:                 B 队 总分 103:
    玩家庚 tank     15            玩家甲 tank     17
    玩家戊 damage   22            玩家乙 damage    9
    玩家壬 damage   17            玩家丙 damage   30
    玩家丁 support  24            玩家己 support  22
    玩家癸 support  21            玩家辛 support  25
分差: 4      缓冲区还剩: 0
```

手动调整的结果原样存进去了，`rating_used` 跟着分到的位置走（玩家庚拖到坦克位，记的是他的坦克分 15）。

### 控制台

无错误。Sortable 从本站 `static/vendor/` 加载，页面里没有任何 CDN 引用，也没有 gravatar 请求（030 那轮关掉了）。

## 几个决定

**满员是拒绝，不是「放进去再标红」。** 屏幕上看到的永远是一个能直接保存的状态，不会出现「11 个人在 A 队」这种需要你回头收拾的中间态。

**位置人数不符只标红，不拦。** 设计 9.5 明写「仍然允许保存（管理员可能有特殊安排）」。所以硬规则只有队伍总人数——那是你要求的；位置数量归设计管，标红即可。

**缓冲区里的人保存后还在。** 写测试时发现这件事我原本没想清楚：保存时把缓冲区的人 `is_selected` 清掉的话，下次打开板子他们就消失了——而缓冲区本来就是「还没想好」的暂存区，存一下人就没了是反的。所以缓冲区的人保留在板子上，只是不在任何队伍里，不进名单也不进复制文本。代码里写了注释说明这个取舍。

**不只能用鼠标。** 每张卡片上有 A / B / 缓冲 三个按钮，走同一套满员规则。上面那三步验证用的就是按钮路径。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
207 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ uv run python -m pytest -q
608 passed in 45.81s

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

新增 7 个测试。

## 拖拽本身没有写成测试

拖拽是浏览器行为，要测得起一个真浏览器跑 JS，慢且脆。写成测试的是**它依赖的东西**：`data-team-size`、`data-zone-capacity`、`data-ratings` 这些属性在不在，Sortable 是不是从本站加载，POST 字段名有没有变。这些一旦被模板改动弄丢，满员规则会**静默失效**——所以钉住它们。

拖拽的实际行为在真实浏览器里验了，输出贴在上面。

## 改动文件

```
scrims/split_admin.py                      zones_for()：按位置分区；bench 上下文
scrims/templates/scrims/admin/split.html   三区板子，替换原来的下拉表格
scrims/templates/scrims/admin/_zone.html   新增：一个投放区
scrims/templates/scrims/admin/_card.html   新增：一张玩家卡片
static/js/scrim-split.js                   重写：Sortable + 满员规则 + 实时算分 + 按钮路径
static/css/scrim-split.css                 重写
scrims/services.py                         save_teams 注释说明缓冲区的语义
scrims/tests/test_teaming.py               新增 7 个测试
```

（删掉了 `_team.html`，它是 021 的下拉表格。）
