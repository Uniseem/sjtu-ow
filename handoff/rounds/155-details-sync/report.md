# 155 细节文档补齐，修一条偶发失败的测试（报告）

## 做了什么

1. `docs/design-details.md`：
   - 4.6 个人主页写成 v6.41 的版式
   - 4.7 筛选写成 v6.40 的做法（带参数实时渲染）
   - 5.3 战队主页加队内联系方式
   - 8 赛事详情加选手联系方式和报名详情页的比赛时间，内战详情加自己的分队和群链接
   - 9 「我的战队」加队内联系方式、「我的报名」加比赛时间
   - 11 「不做」划掉个人主页和成员筛选
   - 头部版本号
2. `conftest.py`：`_rate_limit_window_stays_put`
3. `scripts/screens.py`：加 `mail-tournament-reminder`、`mail-tournament-moved`、`mail-member-left`（截了 375 宽，信件排版正常）
4. 演示站 `/etc/cron.d/sjtu-ow` 的注释

## 命令输出

偶发失败（143 之后第一次见，整组检查里）：

```
FAILED comments/tests/test_comment_extras.py::test_likes_are_rate_limited - a...
E       assert '点赞太频繁' in '\n<section id="slot-article-comments" ...
```

加夹具后，限流相关的 9 个测试文件连跑三遍：

```
229 passed in 32.49s
229 passed in 30.36s
229 passed in 29.64s
```

整组检查（测试机）：

```
1585 条测试分成 4 片
分片 1：397 passed in 36.91s
分片 2：396 passed in 36.46s
分片 3：396 passed in 35.36s
分片 4：396 passed in 37.25s
== 迁移 (00:04:54)
No changes detected
== 生产配置 (00:04:55)
System check identified no issues (0 silenced).
== 错误页和模板一致 (00:04:56)
== Docker 镜像 (00:04:57)
构建成功：72125feaba21
== 全部通过 (00:04:57)
```

## 没做 / 未验证

- 没有「拆掉夹具就红」的测试：原来的失败是概率性的（要刚好跨过整分钟），没法稳定复现；改的是测试的前提，不是网站的规则
- 网站代码没变，演示站只在推送后对齐
