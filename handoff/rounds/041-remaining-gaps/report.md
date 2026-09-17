# 041 实现报告

## 结论

**完成。039 找到的三个测试空白全部补上了**（040 一个，这轮两个）。

**更正 039 的报告**：它说「解散战队改掉第一处（申请入队）没人发现」——**两处都说错了**。这轮逐个变异发现：

- 文件里第一处 `if team.is_disbanded:` 在 `update_team`（改资料），不是申请入队
- **四处全都没有测试**，不是一处

## 解散战队：四处逐个变异

```
  第 109 行 update_team            ✗ 没人发现   650 passed
  第 134 行 can_apply              ✗ 没人发现   652 passed
  第 189 行 approve_application    ✗ 没人发现   652 passed
  第 322 行 disband_team           ✗ 没人发现   652 passed
```

（通过数从 650 变成 652，是因为中途加了签名的两条测试。）

**没有任何测试尝试过在战队解散之后再对它做什么。** 四条各补一条：

| 守卫 | 测试 | 为什么这样构造 |
|---|---|---|
| `can_apply` | 解散后申请入队 → 被拒，提示「已解散」 | 走真实的 `disband_team` |
| `update_team` | 解散后**超级管理员**改资料 → 被拒，队名不变 | 解散会删掉所有成员关系，队长已经不是队长了，只有超管能走到这道闸——**正因为只有超管能走到，它才必须拦得住** |
| `approve_application` | 有待审申请时战队被标记解散 → 不能批准 | `disband_team` 自己会取消待审申请，所以这道闸是给「别的途径标了解散」（后台改、数据修复）兜底的，直接 `update(disbanded_at=...)` 构造 |
| `disband_team` | 解散两次 → 被拒，**原来的解散时间不被覆盖** | 同样只有超管能走到 |

## 签名比对

两条测试：

1. **断言原语**：用 spy 替换 `hmac.compare_digest`，调用 `verify()` 后确认它被调用了。
2. **断言结果**：对的签名通过；十六进制大写也通过；差一位、换密钥、改内容、空签名、`None` 都不通过。

第 1 条是这件事唯一可靠的测法。`==` 的问题是它比较到第一个不同字符就返回，耗时暴露了「前面有几位对了」，攻击者可以逐位试出签名——但这种差异是纳秒级的，要大量采样统计才看得出来，**写成单元测试要么不稳定要么太慢**。断言代码用了哪个原语，比假装端到端验证了诚实。

## 变异测试

```
  ✓ 被抓到  is_disbanded @ update_team         1 failed, 44 passed
  ✓ 被抓到  is_disbanded @ can_apply           1 failed, 44 passed
  ✓ 被抓到  is_disbanded @ approve_application 1 failed, 44 passed
  ✓ 被抓到  is_disbanded @ disband_team        1 failed, 44 passed
  ✓ 被抓到  signing: compare_digest → ==       1 failed, 21 passed
已还原: True
```

五处各被**恰好一条**测试抓到——说明每条测试对准的就是它那道闸，没有互相重叠。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
209 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ uv run python -m pytest -q
656 passed in 51.84s

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

新增 6 个测试，没有改业务代码。

## 改动文件

```
teams/tests/test_teams.py              新增 4 个测试
integrations/tests/test_api_auth.py    新增 2 个测试
handoff/rounds/039-mutation-sweep/report.md   加更正说明
```
