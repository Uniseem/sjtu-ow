# 030 错误码对齐与关闭 gravatar

用户回来后定的两件事：

> 关闭 gravatar。错误码那个你自己看，不影响开发就不管。

## 任务

### T1 关闭 gravatar

`WAGTAIL_GRAVATAR_PROVIDER_URL = None`。

### T2 错误码

用户说「自己看」。我看的结果是**要管**，理由见报告——不是「影响开发」，是我 018 轮的判断本身就错了，而且查下去发现了五处真的不符。

## 验收标准

1. `ruff` / `pytest` / `makemigrations --check` / 生产 `check --deploy` 干净
2. 贴出错误码逐条比对
3. git 提交，信息以 `030:` 开头
