# 121 内容审核：发信要求作者修改（报告）

## 做了什么

1. **记录决定**（用户 2026-10-04：「直接处置只做发信，配色不换」）：设计 v6.17 的 5.5.4（处置动作写成三类：标记、发信要求修改、其余直接处置到各自功能里做）、10.2 邮件清单和 10.3 主题加「要求修改内容」、14.1 写明后台保持 Wagtail 默认配色；STATUS「你已经拍板的」第 31 条
2. **服务**：`moderation.services.author_problem()`（没有作者、作者已停用或注销、没有邮箱时说明原因）和 `ask_author_to_revise()`：检查说明（必填、最多 500 字）和作者，把这条记为「已处置」（处理说明「已发信要求作者修改」），写 Wagtail 操作记录 `moderation.ask_author`（带完整说明），事务提交后发信
3. **信**：`moderation.notifications.revise_letter()`，照 10.3 写成信：「请修改你的战队简介」，写内容类型、内容片段、管理员的说明，「去修改」按类型链到个人中心、战队管理页、我的战队、后台编辑页或评论所在位置（图片没有入口就不放按钮）；进邮件样张页（`ask-author`）
4. **复核页**：「要求作者修改」一块：能发时是一个文本框和「发信给作者」（先确认），不能发时写原因；处理记录表把发信也列进去
5. AGENTS：120 的 `.env` 备份位置改成服务器的 `/root/sjtu-ow-backups/`（120 推送后挪出了仓库目录，备份里有密钥）

## 命令输出

变异（`mutate.py`，12 处）。第一次有一处列了两条测试、其中一条没抓到（链接测试只查了队名、没查战队简介，另一条测试抓到了），补了一个断言后整组重跑：

```
baseline green, 5 tests
caught no mail goes out -> test_an_editor_writes_to_the_author
caught the item stays pending -> test_an_editor_writes_to_the_author
caught the message is not kept -> test_an_editor_writes_to_the_author
caught the history hides the mail -> test_an_editor_writes_to_the_author
caught the letter leaves out the message -> test_an_editor_writes_to_the_author
caught teams have nowhere to fix it -> test_an_editor_writes_to_the_author
caught teams have nowhere to fix it -> test_each_kind_of_content_has_somewhere_to_fix_it
caught deactivated authors get mail -> test_no_author_or_a_deactivated_one_gets_no_form_and_no_mail
caught the page offers the form anyway -> test_no_author_or_a_deactivated_one_gets_no_form_and_no_mail
caught the service skips the author check -> test_no_author_or_a_deactivated_one_gets_no_form_and_no_mail
caught an empty message goes out -> test_an_empty_or_long_message_is_refused
caught a long message goes out -> test_an_empty_or_long_message_is_refused
caught anyone may write -> test_only_reviewers_can_write
restored and green; missed: none
```

整组检查：

```
All checks passed!
295 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
1439 passed in 172.46s (0:02:52)
```

演示站：镜像时间 `2026-10-03 19:01:03 +0200`，「No migrations to apply.」，全量生成「成功 46，失败 0」，健康检查 ok。

## 没做 / 未验证

- 演示站没配 SMTP（演示用户的邮箱都是 `demo.example.com`），信在演示站上发不出去；本机用测试邮箱验证了内容
