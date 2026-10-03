# 143 报名中的赛事卡也写比赛日期（报告）

## 做了什么

1. `templates/components/tournament_card.html`：报名中、即将开始报名两支加 `<span data-card-starts>MM.DD 比赛</span>`（日期行本来就是可折行的 flex，手机上会换行）
2. `content/templates/content/home_page.html`：大图卡事实行「报名截止 … · MM.DD 比赛 · 已通过 N 队」
3. 设计 v6.38（5.2），`docs/design-details.md` 赛事卡一条
4. 测试：`core/tests/test_arena_pages.py`、`content/tests/test_home_sections.py` 各加 1 条

## 截图

手机宽度（375×812，浅色）截了 `/teams/?role=support`、`/teams/`、`/tournaments/`、`/scrims/`（演示站，未登录），脚本是 106 的 `cdp_shoot.py` 改成空闲端口、按配置目录名关进程（AGENTS.md 的坑），放在会话临时目录。只看出赛事卡少了比赛日期这一处。

## 命令输出

变异（测试机，4 处，第一次全部被抓到）：

```
baseline green, 2 tests
caught open cards leave the date out -> test_open_and_upcoming_cards_say_when_they_play
caught upcoming cards leave the date out -> test_open_and_upcoming_cards_say_when_they_play
caught a date line even without a date -> test_open_and_upcoming_cards_say_when_they_play
caught the homepage card leaves it out -> test_the_feature_card_says_when_they_play
restored and green; missed: none
```

整组检查（测试机）。前两次在 Tailwind 那一步和 Docker 镜像那一步失败，都是下载 Tailwind 命令行时 GitHub 返回 503（下一轮处理）；第三次：

```
1559 条测试分成 4 片
分片 1：390 passed in 38.42s
分片 2：390 passed in 35.85s
分片 3：390 passed in 36.93s
分片 4：389 passed in 36.53s
== 迁移 (21:59:17)
No changes detected
== 生产配置 (21:59:18)
System check identified no issues (0 silenced).
== 错误页和模板一致 (21:59:19)
== Docker 镜像 (21:59:20)
构建成功：4ab1dc714a33
== 全部通过 (21:59:20)
```

（这次检查时工作区里还有下一轮对 `scripts/check.sh` 的改动，不在本轮提交里）

演示站升级后 `/tournaments/`：

```
data-card-starts>10.25 比赛
data-card-starts>11.08 比赛
```

## 没做 / 未验证

- 没登录状态下的页面才截了图；个人中心、后台没截
