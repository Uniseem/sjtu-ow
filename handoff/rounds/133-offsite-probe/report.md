# 133 全站设置加「测试对象存储」（报告）

## 做了什么

1. `core/offsite.py`：`probe()`，键名 `前缀/sjtu-ow-probe-年月日-时分秒.txt`（不是备份的命名，清理旧备份不会碰它；反正立刻删）。四种失败各一句话：缺哪几项设置、连不上、写入失败、写入成功但删除失败（顺带说明没有删除权限的话旧备份也清不掉）
2. `core/views.py`：`try_offsite_backup`（POST，要 `core.change_sitesettings`），结果放在后台消息里，回到全站设置页
3. `core/wagtail_hooks.py`：后台地址 `settings/core/try-offsite/`
4. `templates/wagtailsettings/edit.html`：按钮和说明
5. `core/admin_setup.py`：上线清单「密钥有了、上传没开」那条提示里加上先测
6. 设计 v6.28（16.7、后台表），README 备份一节

## 命令输出

变异（测试机，8 处，第一次全部被抓到）：

```
baseline green, 4 tests
caught the probe file is left behind -> test_the_probe_writes_then_cleans_up
caught half-filled settings are tried anyway -> test_the_probe_says_which_step_failed
caught a failed write is not explained -> test_the_probe_says_which_step_failed
caught a failed delete is not explained -> test_the_probe_says_which_step_failed
caught no word about the missing key -> test_the_probe_works_before_uploading_is_on
caught no word about switching uploads on -> test_the_probe_works_before_uploading_is_on
caught anyone in the admin may run it -> test_the_settings_page_button
caught no button on the settings page -> test_the_settings_page_button
restored and green; missed: none
```

整组检查（测试机）：

```
1513 条测试分成 4 片
分片 1：379 passed in 36.11s
分片 2：378 passed in 36.56s
分片 3：378 passed in 34.33s
分片 4：378 passed in 33.53s
== 迁移 (20:28:43)
No changes detected
== 生产配置 (20:28:44)
System check identified no issues (0 silenced).
== 错误页和模板一致 (20:28:45)
== Docker 镜像 (20:28:46)
构建成功：d1b7909ccb83
== 全部通过 (20:28:46)
```

演示站已升级（没有迁移）。

## 没做 / 未验证

- 没有连真的对象存储试（没有可用的存储桶；测试用的是假的客户端，和现有的异地备份测试一样）。boto3 的 `put_object`、`delete_object` 参数是按文档写的
- 测试时内容编辑被 Wagtail 转回后台首页（302），不是 403：Wagtail 对后台里的 `PermissionDenied` 就是这样处理的
