# 234 M2 第四轮：接口封装和前台路由

## 背景

233 把页头页脚立起来了，导航指向的地址大多还不存在，一点进去就是整页 404。接口还是 apigen 生成的裸 `fetch`，401、待发信和幂等键都没包。这一轮做 12 号文档 6.4 的封装，并按 02 号文档第 2、3 节把会打开成页面的地址登记上（6.3）。

## 本轮范围

### 做

1. `web/packages/api` 的调用封装：错误变成带状态码的 `ApiError`；401 跳 `/accounts/login/?next=`；响应里有 `letters.batch` 就跳 `/letters/<batch>/?back=`（当前地址在 `/admin/` 下则去 `/admin/letters/<batch>/`）；POST/PUT/PATCH/DELETE 带 `Idempotency-Key`，调用方传入的键原样沿用。写成功后通知外面刷新会话。
2. 前台 GET 页面按 02 号文档第 2、3 节登记，外加导航里已有的 `/news/`、`/about/`、`/terms/`、`/privacy/`。编号参数用 `:id(\\d{1,18})`。页面先只显示标题，数据等接口有了再接。
3. 不登记的：只接受 POST 的动作、`/healthz`、图标、sitemap、robots、HTMX 片段、文件下载。那些不是给 SSR 画的页。

### 不做

- 每个页面的真实内容和接口。
- `/_styleguide/` 的组件样张（M2 还欠的那一项，下一轮）。
- 体积预算进 CI、字体。
- 正式站。

## 验收标准

测试机上 `pnpm test` 通过。封装的三处变异（不跳 401、写请求不带幂等键、待发信跳错地址）和「拿掉 `/news/`」先红再改回。
