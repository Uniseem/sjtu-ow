# 061 有有效报名的战队不能解散

## 背景

059 的守卫变异扫描里，`disband_team` 的 `if blockers` 幸存——因为 `disband_blockers()` **永远返回空列表**：

```python
def disband_blockers(team) -> list[str]:
    """Reasons the team cannot be disbanded.

    M4 adds the real check: a team with a registration that is pending,
    awaiting upstream, or approved on a draft/published tournament must
    withdraw it first (design 7.5).
    """
    return []
```

M4（014–016 轮）做完报名后没人回来接。设计 7.5：

> **限制**：战队不能有「有效报名」。有效报名指：赛事状态为草稿或已发布，且报名状态为待审核、待上游确认或已通过。有有效报名时提示先撤回报名

**现在有有效报名的战队也能解散**：报名还挂在赛事里，名单还在，队伍已经没了。058 的注销流程要求队长先解散或转让，也会绕过这个限制。

同文件还有一个 `blocked_query()`，注释「Placeholder so M4 can express "teams with live registrations"」，返回空条件，**没有任何地方调用**。

## 任务

1. `disband_blockers()` 按设计 7.5 实现：列出每个有效报名所在的赛事，提示先撤回
2. 队长和超级管理员都受这个限制（设计 7.5 没有区分）
3. 删掉 `blocked_query()`
4. 测试：待审核、待上游确认、已通过的报名挡住解散；草稿赛事的也挡；已驳回、已撤回的不挡；赛事已结束、已取消的不挡；撤回之后能解散
5. 逐项变异

## 验收标准

本地四项检查干净，推送后 CI 绿；测试机更新。
