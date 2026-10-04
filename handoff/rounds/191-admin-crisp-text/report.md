# 191 后台文字发虚（报告）

## 做了什么

1. `static/css/admin.css`：`body { font-size: 14px; }`（Wagtail 原来是 85%，13.6px）
2. 字体栈改成 `-apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Source Han Sans SC", "Noto Sans SC", sans-serif`（去掉了 HarmonyOS Sans、MiSans，雅黑排到苹方前面）
3. `--w-color-text-meta` 从 `fg-3` 改成 `fg-2`，侧栏菜单文字 `--w-color-text-label-menus-default` 从 `fg-2` 改成 `fg`
4. 设计 14.1（v6.69）
5. `core/tests/test_admin_look.py` 加一条

开发者这台电脑的字体目录里只有 `msyh.ttc`、`msyhbd.ttc`、`msyhl.ttc`（微软雅黑），没有苹方，所以这台机器上发虚的原因是非整数字号；苹方那条是给装了苹方的 Windows 电脑预防的。无头 Edge 截图看不出 Windows 上的发虚（不走 ClearType），只确认了改成 14px 后赛事列表、首页布局没被撑乱。**是否真的不糊，要用户在自己电脑上看**，未验证。

## 命令输出

变异（本机，4 处，全部被抓到）：

```
baseline green, 1 tests
caught Wagtail's 13.6px back -> test_admin_text_is_whole_pixels_with_yahei_before_pingfang
caught 苹方 first again -> test_admin_text_is_whole_pixels_with_yahei_before_pingfang
caught faint meta text -> test_admin_text_is_whole_pixels_with_yahei_before_pingfang
caught faint menu text -> test_admin_text_is_whole_pixels_with_yahei_before_pingfang
restored and green; missed: none
```

整组检查（本机；测试机仍连不上）：

```
357 files already formatted
1727 passed, 1 skipped in 295.95s (0:04:55)
No changes detected
```

正式站已升级（`deploy_ship.sh 191`）。

## 没做

- 前台的字体栈也是苹方在雅黑前面（前台正文 16px，用户没觉得糊），没改
