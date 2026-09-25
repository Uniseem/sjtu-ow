# integrations

开放 API 与 Webhook 在 067 轮随本站独立一起删除（设计 v1.6，第 11 章）。

这个包只剩迁移历史：`tournaments/migrations/0004` 依赖 `integrations/0001`，
所以包必须留在 `INSTALLED_APPS` 里，迁移文件不能删。`0003` 删掉了三张表和排队中的
Webhook 任务。不要往这里加代码。
