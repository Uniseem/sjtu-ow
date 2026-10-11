# 对拍报告

98 / 98 通过（像素差上限 0.5%，通道差 18）

| 结论 | 身份 | 地址 | 状态（旧/新） | 问题 |
|---|---|---|---|---|
| 通过 | visitor | `/accounts/login/` | 200 / 200 |  |
| 通过 | visitor | `/accounts/signup/` | 200 / 200 |  |
| 通过 | visitor | `/accounts/confirm-email/?email=pending@screens.test` | 200 / 200 |  |
| 通过 | visitor | `/accounts/logout/` | 302 / 302 |  |
| 通过 | visitor | `/accounts/inactive/` | 200 / 200 |  |
| 通过 | visitor | `/accounts/reauthenticate/` | 302 / 302 |  |
| 通过 | visitor | `/accounts/email/` | 302 / 302 |  |
| 通过 | visitor | `/accounts/password/change/` | 302 / 302 |  |
| 通过 | visitor | `/accounts/password/set/` | 302 / 302 |  |
| 通过 | visitor | `/accounts/password/reset/` | 200 / 200 |  |
| 通过 | visitor | `/accounts/password/reset/confirm/?email=member@screens.test` | 200 / 200 |  |
| 通过 | visitor | `/accounts/password/reset/complete/` | 200 / 200 |  |
| 通过 | visitor | `/accounts/password/reset/done/` | 200 / 200 |  |
| 通过 | visitor | `/accounts/login/code/confirm/` | 302 / 302 |  |
| 通过 | member | `/accounts/login/` | 302 / 302 |  |
| 通过 | member | `/accounts/signup/` | 302 / 302 |  |
| 通过 | member | `/accounts/confirm-email/?mode=change&email=pending-member@screens.test` | 200 / 200 |  |
| 通过 | member | `/accounts/logout/` | 200 / 200 |  |
| 通过 | member | `/accounts/inactive/` | 200 / 200 |  |
| 通过 | member | `/accounts/reauthenticate/` | 200 / 200 |  |
| 通过 | member | `/accounts/email/` | 200 / 200 |  |
| 通过 | member | `/accounts/password/change/` | 200 / 200 |  |
| 通过 | member | `/accounts/password/set/` | 302 / 301 | 已批准差异：docs/frontend-migration.md §10 #5（266）：未使用的设密码入口301回账号安全 |
| 通过 | member | `/accounts/password/reset/` | 200 / 200 |  |
| 通过 | member | `/accounts/password/reset/confirm/?email=member@screens.test` | 200 / 200 |  |
| 通过 | member | `/accounts/password/reset/complete/` | 200 / 200 |  |
| 通过 | member | `/accounts/password/reset/done/` | 200 / 200 |  |
| 通过 | member | `/accounts/login/code/confirm/` | 302 / 302 |  |
| 通过 | captain | `/accounts/login/` | 302 / 302 |  |
| 通过 | captain | `/accounts/signup/` | 302 / 302 |  |
| 通过 | captain | `/accounts/confirm-email/?mode=change&email=pending-captain@screens.test` | 200 / 200 |  |
| 通过 | captain | `/accounts/logout/` | 200 / 200 |  |
| 通过 | captain | `/accounts/inactive/` | 200 / 200 |  |
| 通过 | captain | `/accounts/reauthenticate/` | 200 / 200 |  |
| 通过 | captain | `/accounts/email/` | 200 / 200 |  |
| 通过 | captain | `/accounts/password/change/` | 200 / 200 |  |
| 通过 | captain | `/accounts/password/set/` | 302 / 301 | 已批准差异：docs/frontend-migration.md §10 #5（266）：未使用的设密码入口301回账号安全 |
| 通过 | captain | `/accounts/password/reset/` | 200 / 200 |  |
| 通过 | captain | `/accounts/password/reset/confirm/?email=captain@screens.test` | 200 / 200 |  |
| 通过 | captain | `/accounts/password/reset/complete/` | 200 / 200 |  |
| 通过 | captain | `/accounts/password/reset/done/` | 200 / 200 |  |
| 通过 | captain | `/accounts/login/code/confirm/` | 302 / 302 |  |
| 通过 | tournament_admin | `/accounts/login/` | 302 / 302 |  |
| 通过 | tournament_admin | `/accounts/signup/` | 302 / 302 |  |
| 通过 | tournament_admin | `/accounts/confirm-email/?mode=change&email=pending-tournament_admin@screens.test` | 200 / 200 |  |
| 通过 | tournament_admin | `/accounts/logout/` | 200 / 200 |  |
| 通过 | tournament_admin | `/accounts/inactive/` | 200 / 200 |  |
| 通过 | tournament_admin | `/accounts/reauthenticate/` | 200 / 200 |  |
| 通过 | tournament_admin | `/accounts/email/` | 200 / 200 |  |
| 通过 | tournament_admin | `/accounts/password/change/` | 200 / 200 |  |
| 通过 | tournament_admin | `/accounts/password/set/` | 302 / 301 | 已批准差异：docs/frontend-migration.md §10 #5（266）：未使用的设密码入口301回账号安全 |
| 通过 | tournament_admin | `/accounts/password/reset/` | 200 / 200 |  |
| 通过 | tournament_admin | `/accounts/password/reset/confirm/?email=tournament_admin@screens.test` | 200 / 200 |  |
| 通过 | tournament_admin | `/accounts/password/reset/complete/` | 200 / 200 |  |
| 通过 | tournament_admin | `/accounts/password/reset/done/` | 200 / 200 |  |
| 通过 | tournament_admin | `/accounts/login/code/confirm/` | 302 / 302 |  |
| 通过 | scrim_admin | `/accounts/login/` | 302 / 302 |  |
| 通过 | scrim_admin | `/accounts/signup/` | 302 / 302 |  |
| 通过 | scrim_admin | `/accounts/confirm-email/?mode=change&email=pending-scrim_admin@screens.test` | 200 / 200 |  |
| 通过 | scrim_admin | `/accounts/logout/` | 200 / 200 |  |
| 通过 | scrim_admin | `/accounts/inactive/` | 200 / 200 |  |
| 通过 | scrim_admin | `/accounts/reauthenticate/` | 200 / 200 |  |
| 通过 | scrim_admin | `/accounts/email/` | 200 / 200 |  |
| 通过 | scrim_admin | `/accounts/password/change/` | 200 / 200 |  |
| 通过 | scrim_admin | `/accounts/password/set/` | 302 / 301 | 已批准差异：docs/frontend-migration.md §10 #5（266）：未使用的设密码入口301回账号安全 |
| 通过 | scrim_admin | `/accounts/password/reset/` | 200 / 200 |  |
| 通过 | scrim_admin | `/accounts/password/reset/confirm/?email=scrim_admin@screens.test` | 200 / 200 |  |
| 通过 | scrim_admin | `/accounts/password/reset/complete/` | 200 / 200 |  |
| 通过 | scrim_admin | `/accounts/password/reset/done/` | 200 / 200 |  |
| 通过 | scrim_admin | `/accounts/login/code/confirm/` | 302 / 302 |  |
| 通过 | content_editor | `/accounts/login/` | 302 / 302 |  |
| 通过 | content_editor | `/accounts/signup/` | 302 / 302 |  |
| 通过 | content_editor | `/accounts/confirm-email/?mode=change&email=pending-content_editor@screens.test` | 200 / 200 |  |
| 通过 | content_editor | `/accounts/logout/` | 200 / 200 |  |
| 通过 | content_editor | `/accounts/inactive/` | 200 / 200 |  |
| 通过 | content_editor | `/accounts/reauthenticate/` | 200 / 200 |  |
| 通过 | content_editor | `/accounts/email/` | 200 / 200 |  |
| 通过 | content_editor | `/accounts/password/change/` | 200 / 200 |  |
| 通过 | content_editor | `/accounts/password/set/` | 302 / 301 | 已批准差异：docs/frontend-migration.md §10 #5（266）：未使用的设密码入口301回账号安全 |
| 通过 | content_editor | `/accounts/password/reset/` | 200 / 200 |  |
| 通过 | content_editor | `/accounts/password/reset/confirm/?email=content_editor@screens.test` | 200 / 200 |  |
| 通过 | content_editor | `/accounts/password/reset/complete/` | 200 / 200 |  |
| 通过 | content_editor | `/accounts/password/reset/done/` | 200 / 200 |  |
| 通过 | content_editor | `/accounts/login/code/confirm/` | 302 / 302 |  |
| 通过 | officer | `/accounts/login/` | 302 / 302 |  |
| 通过 | officer | `/accounts/signup/` | 302 / 302 |  |
| 通过 | officer | `/accounts/confirm-email/?mode=change&email=pending-officer@screens.test` | 200 / 200 |  |
| 通过 | officer | `/accounts/logout/` | 200 / 200 |  |
| 通过 | officer | `/accounts/inactive/` | 200 / 200 |  |
| 通过 | officer | `/accounts/reauthenticate/` | 200 / 200 |  |
| 通过 | officer | `/accounts/email/` | 200 / 200 |  |
| 通过 | officer | `/accounts/password/change/` | 200 / 200 |  |
| 通过 | officer | `/accounts/password/set/` | 302 / 301 | 已批准差异：docs/frontend-migration.md §10 #5（266）：未使用的设密码入口301回账号安全 |
| 通过 | officer | `/accounts/password/reset/` | 200 / 200 |  |
| 通过 | officer | `/accounts/password/reset/confirm/?email=officer@screens.test` | 200 / 200 |  |
| 通过 | officer | `/accounts/password/reset/complete/` | 200 / 200 |  |
| 通过 | officer | `/accounts/password/reset/done/` | 200 / 200 |  |
| 通过 | officer | `/accounts/login/code/confirm/` | 302 / 302 |  |
