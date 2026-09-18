# 064 worker 读不到静态文件，事件触发的预渲染全部失败

## 背景

063 部署后发布隐私政策，预渲染的静态页 25 秒后还是旧的。worker 日志：

```
UserWarning: No directory at: /app/staticfiles/
预渲染失败 /privacy/：渲染出错：Missing staticfiles manifest entry for 'css/error.css'
```

`deploy/docker-compose.yml` 里 `worker` 没挂 `static` 卷。生产配置用带清单的静态文件存储，渲染任何引用静态文件的模板都要读 `collectstatic` 生成的清单，worker 读不到就出错。设计 16.x 的数据卷表也只写了「`web` 写入，`proxy` 读取」——**设计本身就漏了**。

影响：设计 13.13.4 事件表的 14 行在服务器上都不生效，静态页要等每天 04:15 在 `web` 里跑的全量生成才更新，最长旧一天。任务记为成功，`/healthz` 看不出来；失败只记在后台「半静态渲染」页，测试机上还没有管理员账号。

## 任务

1. 设计先改：数据卷表 `static` 一行写明 `worker` 读取（预渲染要读清单），附录 D 记版本
2. `worker` 挂 `static:/app/staticfiles:ro`
3. **清单要跟上新版本**：升级时 `web` 和 `worker` 同时重建，`web` 启动时才跑 `collectstatic`。Django 的清单存储每个进程只读一次，worker 如果在 `collectstatic` 写完之前渲染了一页，就会一直用旧版本的清单，写出指向旧 CSS 的静态页（旧文件 30 天后被清理，页面就没样式了）。预渲染前检查清单文件变没变，变了就重新读
   - 不用 `depends_on: condition: service_healthy`：`/healthz` 要求 worker 心跳，web 等不到 worker 就不健康，worker 又等 web 健康，第一次启动会互相卡住
4. 测试 + 变异
5. 测试机上**真的触发一次事件**，看静态页变了、失败记录清零

## 验收标准

本地四项检查干净，推送后 CI 绿；测试机上改一次内容后静态页在一分钟内更新，`PrerenderedPage` 没有失败记录。
