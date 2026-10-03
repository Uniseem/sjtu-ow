# 144 Tailwind 命令行不再每次重新下载（报告）

## 做了什么

1. `deploy/fetch_tailwind_cli.py`（新）：`arch()`、`url()`、`target_name()`、`fetch()`（重试 5 次，间隔递增，写 `.part` 再改名，`chmod 755`）
2. `Dockerfile`：uv 之后、依赖之前加 `ARG TAILWIND_CLI_VERSION=2.9.0`，`COPY` 脚本并运行；后面的 `RUN` 去掉 `tailwind download_cli`
3. `scripts/check.sh`：`ls .django_tailwind_cli/tailwindcss* || download_cli`
4. `core/tests/test_tailwind_cli_fetch.py`（7 条）
5. AGENTS.md「已知的坑」一条

## 命令输出

143 时的失败（测试机）：

```
❌ Command error: Failed to download Tailwind CSS CLI: HTTP 503: Service Unavailable
CommandError: Failed to download Tailwind CSS CLI: HTTP 503: Service Unavailable
```

和 Docker 那一步：

```
ERROR: failed to build: failed to solve: process "/bin/sh -c chmod +x ... && uv run python manage.py tailwind download_cli && uv run python manage.py tailwind build" did not complete successfully: exit code: 1
```

测试机上那个文件的修改时间（`21:43`，就是上一次检查的时候）：

```
-rwxr-xr-x  1 root root 112068736 Oct  3 21:43 tailwindcss-extra-linux-x64-2.9.0
```

变异（测试机，6 处，第一次全部被抓到）：

```
baseline green, 6 tests
caught the image pins another version -> test_the_image_pins_the_same_version_as_the_settings
caught the image downloads again -> test_the_image_fetches_before_the_code_and_never_redownloads
caught the checks download every time -> test_the_check_script_downloads_only_when_missing
caught no second try -> test_a_flaky_download_is_retried
caught a name django-tailwind-cli does not know -> test_names_match_what_django_tailwind_cli_expects
caught a name django-tailwind-cli does not know -> test_names_per_architecture
caught not executable -> test_a_flaky_download_is_retried
restored and green; missed: none
```

整组检查（测试机，镜像用新 Dockerfile 构建）：

```
1566 条测试分成 4 片
分片 1：392 passed in 47.39s
分片 2：392 passed in 45.05s
分片 3：391 passed in 43.91s
分片 4：391 passed in 45.67s
== 迁移 (22:05:04)
No changes detected
== 生产配置 (22:05:05)
System check identified no issues (0 silenced).
== 错误页和模板一致 (22:05:06)
== Docker 镜像 (22:05:07)
构建成功：3e839f830804
== 全部通过 (22:05:07)
```

再构建一次，下载那一层是缓存：

```
#13 [stage-0  6/10] RUN python /tmp/fetch_tailwind_cli.py "2.9.0" /app/.django_tailwind_cli
#13 CACHED
```

演示站升级（第一次用新 Dockerfile 构建，下载了一次）：

```
全量生成完成：成功 46，失败 0，删除 0；目录占用 1607 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

## 没做 / 未验证

- arm64 的机器上没试（名字按 tailwind-cli-extra 的发布文件写的）
- 下载的文件不校验哈希：和原来 django-tailwind-cli 的做法一样
