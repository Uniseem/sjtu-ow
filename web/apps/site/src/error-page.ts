// The error pages, word for word from templates/errors/*.html (design 13.15,
// frontend-migration A12): their own small document with error.css, no
// site stylesheet, no script, nothing to hydrate. 503 is the old
// maintenance page: what the visitor sees when Go cannot be reached.

export type ErrorStatus = 403 | 404 | 429 | 500 | 503

type Body = { title: string; code: string; html: string }

function escape(text: string): string {
  return text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;")
}

function body(status: ErrorStatus, requestId: string | null): Body {
  switch (status) {
    case 403:
      return {
        title: "没有权限 · SJTU-OW",
        code: "403",
        html: `<h1>没有权限</h1>
      <p>你没有权限查看这个页面。</p>
      <p>如果尚未登录，请先登录后再试。</p>
      <div class="actions">
        <a href="/accounts/login/">去登录</a>
        <a class="secondary" href="/">回到首页</a>
      </div>`,
      }
    case 429:
      return {
        title: "操作太频繁 · SJTU-OW",
        code: "429",
        html: `<h1>操作太频繁</h1>
      <p>请稍后再试。</p>
      <div class="actions">
        <a href="/">回到首页</a>
      </div>`,
      }
    case 500:
      return {
        title: "服务器出错 · SJTU-OW",
        code: "500",
        html: `<h1>服务器出错了</h1>
      <p>请稍后再试。向管理员反馈时，请附上下面的请求编号。</p>
      ${requestId ? `<p class="request-id">请求编号：${escape(requestId)}</p>` : "<p>当前没有请求编号。</p>"}
      <div class="actions">
        <a href="/">回到首页</a>
      </div>`,
      }
    case 503:
      return {
        title: "维护中 · SJTU-OW",
        code: "503",
        html: `<h1>网站维护中</h1>
      <p>
        正在升级或暂时无法处理新的请求。已经生成的公开页面仍然可以浏览，请稍后再试需要登录或提交的操作。
      </p>
      <div class="actions">
        <a href="/">回到首页</a>
      </div>`,
      }
    default:
      return {
        title: "页面不存在 · SJTU-OW",
        code: "404",
        html: `<h1>页面不存在</h1>
      <p>内容可能已经下线，或者网址有误。</p>
      <div class="actions">
        <a href="/">回到首页</a>
        <a class="secondary" href="/tournaments/">查看赛事</a>
        <a class="secondary" href="/teams/">浏览战队</a>
      </div>`,
      }
  }
}

export const ERROR_CSS = "/static/css/error.css"

export function errorDocument(status: ErrorStatus, requestId: string | null = null): string {
  const page = body(status, requestId)
  return `<!DOCTYPE html>
<html lang="zh-Hans">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
    <meta name="theme-color" content="#171a20" media="(prefers-color-scheme: dark)">
    <title>${page.title}</title>
    <link rel="stylesheet" href="${ERROR_CSS}">
  </head>
  <body>
    <header>
      <a href="/" class="brand"><svg class="mark" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="9" fill="#a4161a"/><path d="M8 21.5l8-8 8 8" fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/></svg>SJTU-OW</a>
    </header>
    <main>
      <p class="code" aria-hidden="true">${page.code}</p>
      ${page.html}
    </main>
    <footer>学生社团自办网站 · 不是上海交通大学官方网站</footer>
  </body>
</html>
`
}
