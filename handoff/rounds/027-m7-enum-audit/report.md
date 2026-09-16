# 027 实现报告

## 结论

**完成，没有发现不符。** 附录 B 的 18 个枚举，取值和顺序全部和文档一致。

026 查数字时发现了一处不符（邮件前缀），所以这轮不能想当然——逐个打出来比对过了。

## 逐个比对

```
   Registration.status          ['pending', 'awaiting_upstream', 'approved', 'rejected', 'withdrawn']
   Tournament.review_mode       ['local', 'upstream', 'two_stage']
   Tournament.status            ['draft', 'published', 'finished', 'cancelled']
   Scrim.status                 ['draft', 'published', 'finished', 'cancelled']
   Scrim.format                 ['rq_5v5', 'rq_6v6', 'open_5v5', 'open_6v6']
   ScrimSignup.assigned_role    ['tank', 'damage', 'support']
   ScrimSignup.team             ['a', 'b']
   LfgPost.status               ['open', 'full', 'closed']
   TeamApplication.status       ['pending', 'approved', 'rejected', 'cancelled']
   TeamMembership.role          ['captain', 'member']
   PrerenderedPage.status       ['pending', 'ready', 'failed']
   TypographyRule.mode          ['system', 'inherit', 'custom']
   ModerationItem.risk          ['none', 'low', 'medium', 'high', 'unknown']
   ModerationItem.status        ['pending', 'ok', 'handled', 'ignored']
   RegistrationStatusLog.actor_type  ['captain', 'admin', 'upstream', 'system']
   WebhookPayloadMode           ['thin', 'full']
   WebhookDelivery.status       ['pending', 'succeeded', 'failed']
   WebhookEvent                 ['registration.submitted', 'registration.roster_synced',
                                 'registration.withdrawn', 'registration.status_changed', 'ping']
```

全部 ✓。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
204 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ uv run python -m pytest -q
543 passed

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

新增 1 个测试。

## 顺带发现

写测试时踩到三个枚举的类名和我以为的不一样：`LfgPost.Status` 实际是模块级的 `LfgStatus`，`TeamApplication.Status` 是 `ApplicationStatus`，`ModerationItem.Risk` 是模块级的 `Risk`。都是各自轮次的选择，没有问题，但说明**「我以为叫什么」和「实际叫什么」不能省掉验证这一步**——这轮是写测试时当场报错，成本很低；如果是在别处按记忆写代码，就是一个运行时错误。

## 变异测试时踩到的坑

把 `RegistrationStatus.APPROVED` 从 `approved` 改成 `accepted`，测试如期变红：

```
AssertionError: RegistrationStatus: ['pending', 'awaiting_upstream', 'accepted', ...]
                                 != ['pending', 'awaiting_upstream', 'approved', ...]
```

但**改回去之后测试还是红的**——源文件明明已经是 `approved` 了。原因是 `__pycache__` 里的旧字节码没被换掉。清掉 `__pycache__` 就好了。

记一笔：**做变异测试改完再改回来，如果结果不符合预期，先怀疑字节码缓存，再怀疑自己的判断**。这次差点让我以为测试有问题。

## 改动文件

```
core/tests/test_chapter15_audit.py   新增附录 B 的 18 个枚举断言
```
