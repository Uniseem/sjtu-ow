# 080 合并 074–079；daisyUI 扫描测试在 Windows 上误报

## 背景

074–079 是在分支 `claude/nifty-planck-i1qe4u` 上做的（那个会话只能推分支），CI 只在 `main` 上跑，所以这六轮没在 CI 上跑过。用户 2026-09-26 让把分支同步、合并到 `main`，删掉分支。

合并前在本地（Windows）跑整组检查，pytest 有 1 条失败：`core/tests/test_design_system.py::test_front_end_templates_use_no_daisyui_classes`，报 `templates\wagtailusers\users\edit.html: tab-content`。

原因：测试用 `str(path.relative_to(base))` 取相对路径，Windows 上是反斜杠；排除后台模板的片段写的是正斜杠（`templates/wagtail`），匹配不上，后台模板被当成前台模板扫描。CI 在 Linux 上，不受影响。

## 本轮范围

**做**：

1. 分支快进合并到 `main`、推送、看 CI；删掉远端分支
2. 相对路径改成 `as_posix()`，两个系统上都用正斜杠比较

**不做**：别的测试。`relative_to` 在测试里另有两处（`test_chapter15_audit.py:500`、`test_templates.py:17`），都只是把路径拼进报错信息，不参与匹配。

## 验收标准

- Windows 上整组检查全绿
- 这条测试在前台模板混进 daisyUI 类时仍然会红
