# 173 停用、注销的账号的入队申请收尾；注销时每张表怎么处理写成清单（报告）

## 做了什么

1. `teams/services.approve_application`：申请人 `is_active` 为假时，在事务里把申请关掉（`GONE_NOTE`「申请人的账号已注销或停用」），事务提交后抛 `TeamError`「申请人的账号已注销或停用，这条申请已关闭。」（和「已经是成员」同一个写法：在事务里抛会把关闭也回滚掉）
2. `pending_applications`、`remind_captains` 只算在用的申请人；`close_stale_applications` 照样关，申请人停用了就不发信
3. `core/letters.people`：跳过 `.invalid` 结尾的地址（已注销账号的邮箱）
4. `accounts/services.ON_DELETION`：35 个指向用户的字段，注销时各自怎么处理
5. 设计 v6.57（3.8、7.3）
6. `accounts/tests/test_gone_applicants.py`（5 条）

## 写的过程中改正的

第一版还在 `delete_account` 里加了一步「关闭等待中的申请」，测试一跑发现申请早就是「已取消」、备注是空的：注销时调用的 `leave_all_teams` 本来就会撤回等待中的申请（058）。这一步是多余的，删了；清单里写明是 `leave_all_teams` 撤回的。真正的洞只在「管理员停用账号」这条路上（停用不走注销），这一轮修的就是它。

## 命令输出

变异（测试机，7 处，全部被抓到）：

```
baseline green, 4 tests
caught disabled people join -> test_a_disabled_applicant_cannot_be_approved
caught closed without a word -> test_a_disabled_applicant_cannot_be_approved
caught captains still see them -> test_a_disabled_applicant_cannot_be_approved
caught captains reminded of them -> test_no_reminder_or_letter_about_them
caught the expiry letter goes anyway -> test_no_reminder_or_letter_about_them
caught letters to dead addresses -> test_no_letter_goes_to_a_deleted_address
caught a column without a fate -> test_every_column_pointing_at_a_person_has_a_fate_on_deletion
restored and green; missed: none
```

整组检查（测试机）：

```
1643 条测试分成 4 片
分片 1：411 passed in 44.40s
分片 2：411 passed in 37.29s
分片 3：411 passed in 38.39s
分片 4：410 passed in 38.42s
== 全部通过 (05:25:21)
```

演示站升级后看了一眼现有数据：

```
待审批: 3 其中申请人已停用: 0
```

（演示站上没有被这个洞影响的申请。）

## 没做

- 管理员停用账号时没有顺手撤回申请：停用可能是暂时的，申请留着，到 14 天自动关闭；期间队长看不到、点不了通过
  - **175 轮更正**：这句不对。后台用户编辑页停用账号时调 `after_deactivation`，本来就会取消待审批的入队申请（设计 3.7）；173 的测试是直接改 `is_active` 模拟停用，绕过了那一步。没走编辑页的停用路径（174 关掉的批量「设置启用状态」、脚本、命令行）才会留下申请，173 的拦截是给这些情况兜底
- 停用的队长：战队还挂着这个队长，没处理（另一个问题，留给以后）
