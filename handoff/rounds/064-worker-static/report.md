# 064 实现报告

## 结论

**完成。** worker 挂上 `static` 卷（只读），渲染前检查静态文件清单、变了就重新读。测试机上发布一次内容，33 秒后静态页由 worker 更新，9 条预渲染记录全部 `ready`。

## 原因

生产配置的静态文件存储（WhiteNoise 的 `CompressedManifestStaticFilesStorage`）要读 `collectstatic` 生成的 `staticfiles.json` 才能把 `{% static %}` 换成带哈希的地址，读不到就抛 `Missing staticfiles manifest entry`。`web` 挂了 `static` 卷，`worker` 没挂，设计 16 章的数据卷表也只写了「`web` 写入，`proxy` 读取」——照着设计写的 compose，设计本身漏了。

053 起每次部署后的「全量预渲染」都是 `exec web` 跑的，每天 04:15 的兜底也是（crontab 里 `$DC exec -T web python manage.py prerender`），所以静态页最多旧一天，一直没人看出来。

## 改动

1. **设计先改**（v1.5.15）：数据卷表 `static` 一行写明 `worker` 读取及原因
2. `deploy/docker-compose.yml`：`worker` 加 `static:/app/staticfiles:ro`
3. `core/prerender.py` 新增 `refresh_static_manifest()`，`render_html()` 开头调用：
   - 记住上次读到的清单文件的 `(mtime_ns, size)`，变了就在原实例上重新 `load_manifest()`
   - **为什么要**：升级时 `web` 和 `worker` 一起重建，`web` 启动后才跑 `collectstatic`。Django 的清单存储每个进程只读一次；worker 如果在 `collectstatic` 写完前渲染了一页，就会一直用旧清单，写出指向旧 CSS 的页面，30 天后旧文件被清理，页面就没样式了
   - **第一版写错了，是测试抓出来的**：第一版照 Django 自己的 `setting_changed` 处理，把 `staticfiles_storage._wrapped` 重置为 `empty`。但 `staticfiles_storage` 只是 `storages["staticfiles"]` 的懒加载外壳，实例缓存在 `storages` 里，重置外壳拿回来的还是同一个旧实例。测试断言重新读之后地址变成新哈希，失败了；改成在实例上重新读
   - **没用 `depends_on: condition: service_healthy`**：`/healthz` 要求 worker 心跳，web 要等 worker 才健康，worker 又等 web 健康，第一次启动会互相卡住
4. README：worker 为什么要挂静态卷；**部署后验证 worker 做的事要真的触发一次**
5. `AGENTS.md` 加一条坑：在 `web` 里跑通不等于 `worker` 能跑
6. `REVIEW-GUIDE.md` 加一类盲区：只在服务器上才存在的配置

## 测试

- `core/tests/test_prerender_manifest.py` 4 个测试（两个参数化成 Django 和 WhiteNoise 两种存储，共 6 条）：清单改了不重启也能读到新地址（中间先断言「不刷新时还是旧的」，证明确实有缓存）；清单没变不重读；没有清单的存储不处理；每次渲染都先检查清单
- `core/tests/test_healthcheck_script.py` 加 2 条：`web`、`worker` 都挂了 `static` 卷

## 变异

```
KILLED   worker 不挂静态卷  | 1 failed, 21 passed in 0.29s
KILLED   渲染前不检查清单  | 1 failed in 0.24s
KILLED   清单变了也不重读  | 1 failed, 4 passed in 0.26s
KILLED   没变也重读  | 1 failed, 6 passed in 0.20s
KILLED   不记住读过的版本  | 1 failed, 6 passed in 0.25s
```

5/5 被抓到，全部还原。

## 测试机

打补丁部署（提交后再把服务器上的仓库对齐到提交）：

```
--- 1. 升级前备份:
已备份到 /app/backups/sjtu-ow-20260918-183927.tar.gz（0.1 MB）
--- 2. 构建:
 Image sjtu-ow-test-web Built
 Image sjtu-ow-test-worker Built
--- 3. 启动:
 Container sjtu-ow-test-web-1 Started
 Container sjtu-ow-test-worker-1 Started
web: healthy
--- 4. worker 的挂载:
/app/data rw=true
/app/media rw=true
/app/prerendered rw=true
/app/staticfiles rw=false
```

**真的触发一次事件**：在 `web` 里重新发布两个协议页面（页面发布 → 事件表 → 入队，由 worker 执行，合并窗口 30 秒），每 10 秒看一次静态页：

```
10:40:29
已发布「用户协议」
已发布「隐私政策」
10s: 0
20s: 0
30s: 1
10:41:07
Starting worker worker_id=IpRuY9BQMcrD5EgN3cH70bzgrtoyhN1X queues=default

Counter({'ready': 9})
/privacy/ ready 2026-09-18 10:41:02.519496+00:00
/terms/ ready 2026-09-18 10:41:02.385128+00:00
cache-control: public, max-age=0, must-revalidate
```

worker 日志里 063 看到的 `No directory at: /app/staticfiles/` 警告和「预渲染失败」都没有了；`cache-control` 是 Caddyfile 给预渲染页的头，说明看到的确实是静态文件。静态页里引用的样式表：

```
/static/css/app.11b884ce5286.css 200
```

063 留下的问题（隐私政策静态页停在旧文字）也就一起解决了。

**升级时的竞争没在服务器上复现**：要让 worker 恰好在 `collectstatic` 写完前渲染一页，不好构造。靠单元测试（两种存储各一遍）。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
237 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python -m pytest -q
847 passed in 53.57s
```

839 → 847。

## 顺带想到的（不在本轮做）

- **预渲染失败不够显眼**：任务记为成功，失败只写在 `PrerenderedPage` 表和后台「半静态渲染」页。这次是测试机上没有管理员才没人看见；上线后有管理员，但也要有人去看那一页。可以考虑让 `/healthz` 或后台首页提示「有 N 个页面生成失败」——要改设计 16 章健康检查表，留给以后，**要不要做由用户定**
- worker 还做邮件、Webhook、字体处理，这几样在服务器上都还没真跑过（没有发信服务、没有上游、没传过字体）。字体处理要写 `media`，worker 挂了 `media`，按理没问题，但**未验证**

## 改动文件

```
docs/design.md                           数据卷表、附录 D（v1.5.15）
deploy/docker-compose.yml                worker 挂 static（只读）
core/prerender.py                        refresh_static_manifest
core/tests/test_prerender_manifest.py    新建，6 条
core/tests/test_healthcheck_script.py    2 条
README.md、AGENTS.md、handoff/REVIEW-GUIDE.md
handoff/STATUS.md
handoff/rounds/064-worker-static/
```
