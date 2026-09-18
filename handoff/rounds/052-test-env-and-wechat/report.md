# 052 实现报告

## 结论

**完成。** 设计 16.10 的测试环境横幅和禁止抓取、16.9 的微信内置浏览器提示都实现了。测试机上部署时设 `TEST_ENVIRONMENT=1` 即可。

## 实现

### 测试环境（16.10）

- 新环境变量 `TEST_ENVIRONMENT`，默认关（`sjtu_ow/settings/base.py`）
- 新的模板上下文处理器 `core.context_processors.site_environment`，把它传给所有模板
- `templates/base.html`：打开时在导航栏上面显示一条黄色横幅「测试环境：这里不是正式网站，数据随时可能被清空」
- `content/views.py` 的 `robots_txt`：打开时只返回 `User-agent: *` 和 `Disallow: /`，不再给 sitemap

**预渲染的静态页也有横幅**：大部分访客拿到的是预渲染的静态文件，横幅要在生成时就写进去。预渲染本来就是走 Django 渲染整页，上下文处理器照样生效，补了一条测试确认。

### 微信提示（16.9）

公开页面是预渲染的，**同一份 HTML 发给所有人，服务器看不到访客用的什么浏览器**。所以：

- `base.html` 里放一个默认隐藏（`hidden`）的提示条「点右上角菜单，在浏览器中打开」
- `static/js/app.js` 判断 `navigator.userAgent` 里有没有 `MicroMessenger`，有才显示

CSP 不许内联脚本，判断写在已有的 `app.js` 里。

### 文档

- 设计 16.3 环境变量表加 `TEST_ENVIRONMENT`，16.10 写明由它打开，附录 D 记 v1.5.12
- `README.md` 环境区别表、`.env.example` 同步

## 变异测试

逐项改坏，跑相关的三个测试文件：

```
✓ 被抓到 robots 不看测试环境 | 1 failed, 54 passed in 5.05s ['test_robots_disallows_everything_in_the_test_environment']
✓ 被抓到 上下文不传测试环境 | 2 failed, 53 passed in 5.28s ['test_the_test_environment_banner_appears_only_in_the_test_environment', 'test_a_prerendered_page_carries_the_test_environment_banner']
✓ 被抓到 横幅无条件显示 | 1 failed, 54 passed in 4.75s ['test_the_test_environment_banner_appears_only_in_the_test_environment']
✓ 被抓到 横幅永远不显示 | 2 failed, 53 passed in 4.90s ['test_the_test_environment_banner_appears_only_in_the_test_environment', 'test_a_prerendered_page_carries_the_test_environment_banner']
✓ 被抓到 微信提示去掉 hidden | 1 failed, 54 passed in 4.79s ['test_every_page_carries_a_hidden_wechat_hint']
✓ 被抓到 删掉微信提示 | 1 failed, 54 passed in 4.81s ['test_every_page_carries_a_hidden_wechat_hint']
✓ 被抓到 脚本不判断微信 | 1 failed, 54 passed in 4.81s ['test_app_js_reveals_the_wechat_hint_for_wechat_only']
全部还原
```

## 真浏览器验证

本地起了一个 `TEST_ENVIRONMENT=1` 的开发服务器（8052 端口；8000 上已有别人开的开发服务器，没动它），用内置浏览器打开：

**普通浏览器**：

```
{"banner": "测试环境：这里不是正式网站，数据随时可能被清空",
 "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/",
 "wechatHidden": true}
```

**把 UA 改成 iPhone 微信**（`... MicroMessenger/8.0.50 ...`），再执行一次 `app.js`：

```
{"text": "点右上角菜单，在浏览器中打开", "ua": true, "wechatHidden": false}
```

截图里横幅和提示条都在导航栏上方。**robots**：

```
User-agent: *
Disallow: /
```

浏览器控制台没有报错（CSP 没拦任何东西）。

验证前重新编译了一次 Tailwind：新横幅用了 `bg-warning`、`bg-info`，旧的编译结果里没有这两个样式。部署时镜像里会重新编译，不受影响。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
213 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python -m pytest -q
680 passed in 48.10s
```

675 → 680。推送后的 CI 结果记在下一轮。

## 改动文件

```
sjtu_ow/settings/base.py          TEST_ENVIRONMENT；注册上下文处理器
core/context_processors.py        site_environment
content/views.py                  robots_txt
templates/base.html               横幅；微信提示
static/js/app.js                  判断微信
.env.example、README.md、docs/design.md
content/tests/test_content.py     1 条
core/tests/test_pages.py          3 条
core/tests/test_prerender.py      1 条
handoff/STATUS.md
handoff/rounds/052-test-env-and-wechat/
```
