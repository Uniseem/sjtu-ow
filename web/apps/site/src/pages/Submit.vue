<script lang="ts">
import type { LoadCtx } from "../router"
import { PageRedirect } from "@sjtu-ow/shared/navigation"
import type { ViewerUser } from "../viewer"

export const ARTICLE_NEW = "/admin/articles/new/"
const LOGIN = "/accounts/login/?next=%2Fsubmit%2F"

// content/views.py submit_entry: a contributor goes straight to the editor;
// anyone else is told why not (design 5.4.3). The editor checks again in Go.
export async function load(ctx: LoadCtx) {
  const user: ViewerUser | null = (await ctx.viewer()).user
  if (!user) return { title: "投稿", reasons: ["未登录"], loginUrl: LOGIN }
  const reasons: string[] = []
  if (!user.email_verified) reasons.push("邮箱未验证")
  // Being a contributor (articles.publish_own) needs a verified address, so
  // for an unverified member only can_submit_article tells a ban apart.
  const contributor = user.superuser || user.caps.includes("articles.publish_own")
  const banned = user.email_verified ? !contributor : user.can_submit_article === false
  if (banned) reasons.push("没有投稿权限")
  if (!reasons.length) throw new PageRedirect(ARTICLE_NEW, 302)
  return { title: "投稿", reasons, loginUrl: "" }
}
</script>
<script setup lang="ts">
import { inject } from "vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import { usePageMeta } from "../meta"

const data = inject<{ title: string; reasons: string[]; loginUrl: string }>("page-data")
usePageMeta(() => ({ title: "投稿" }))
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead">
      <div class="l-container">
        <nav class="c-crumbs" aria-label="位置"><a href="/">首页</a><span class="c-crumbs__sep">/</span><a href="/news/">资讯</a><span class="c-crumbs__sep">/</span><span>投稿</span></nav>
        <h1>投稿</h1>
        <p class="c-pagehead__lede">攻略、战报、心得都可以投。稿件在后台写，写完自己点「发布」就出现在资讯里。</p>
      </div>
    </header>
    <div class="l-container pt-8 pb-16 lg:pb-24">
      <div class="c-notice c-notice--warn max-w-2xl">
        <CIcon name="alert" />
        <div class="c-notice__body">
          <p class="font-semibold">目前还不能投稿，原因如下：</p>
          <ul class="mt-2 list-[square] pl-5">
            <li v-for="reason in data?.reasons ?? []" :key="reason">{{ reason }}</li>
          </ul>
        </div>
      </div>
      <div class="mt-6">
        <a v-if="data?.loginUrl" :href="data.loginUrl" class="c-btn c-btn--primary">去登录</a>
        <a v-else href="/me/" class="c-btn c-btn--secondary">返回个人中心</a>
      </div>
    </div>
  </main>
</template>
