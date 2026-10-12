package api

import (
	"fmt"
	"net/http"
)

// LegacyErrorPage is the frozen standalone403/404 document for bookmarked
// file downloads. JSON API errors still use writeError. No API reason or
// private object name is reflected into this document.
func LegacyErrorPage(w http.ResponseWriter, status int) {
	title, body := "页面不存在", `<h1>页面不存在</h1><p>内容可能已经下线，或者网址有误。</p><div class="actions"><a href="/">回到首页</a><a class="secondary" href="/tournaments/">查看赛事</a><a class="secondary" href="/teams/">浏览战队</a></div>`
	if status == http.StatusForbidden {
		title, body = "没有权限", `<h1>没有权限</h1><p>你没有权限查看这个页面。</p><p>如果尚未登录，请先登录后再试。</p><div class="actions"><a href="/accounts/login/">去登录</a><a class="secondary" href="/">回到首页</a></div>`
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(status)
	fmt.Fprintf(w, `<!DOCTYPE html><html lang="zh-Hans"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#171a20" media="(prefers-color-scheme: dark)"><title>%s · SJTU-OW</title><link rel="stylesheet" href="/static/css/error.css"></head><body><header><a href="/" class="brand"><svg class="mark" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="9" fill="#a4161a"/><path d="M8 21.5l8-8 8 8" fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/></svg>SJTU-OW</a></header><main><p class="code" aria-hidden="true">%d</p>%s</main><footer>学生社团自办网站 · 不是上海交通大学官方网站</footer></body></html>`, title, status, body)
}
