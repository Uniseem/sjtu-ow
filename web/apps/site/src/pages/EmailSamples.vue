<script lang="ts">
import { getApiAdminMailSamples } from "@sjtu-ow/api"
import { httpError, type LoadCtx } from "../router"
export async function load(ctx: LoadCtx) {
  const viewer = await ctx.viewer()
  if (!viewer.user?.admin) throw httpError(404)
  return { title: "邮件样张", catalogue: await getApiAdminMailSamples(ctx.api, { legacy: true }) }
}
</script>
<script setup lang="ts">
import { computed, inject } from "vue"
import { useHead } from "@unhead/vue"
import type { GetApiAdminMailSamplesOut } from "@sjtu-ow/api"
const data = inject<{ catalogue: GetApiAdminMailSamplesOut }>("page-data")
const groups = computed(() => {
  const result: { name: string; items: GetApiAdminMailSamplesOut["items"] }[] = []
  for (const sample of data?.catalogue.items ?? []) {
    const last = result.at(-1)
    if (last?.name === sample.group) last.items.push(sample)
    else result.push({ name: sample.group, items: [sample] })
  }
  return result
})
useHead({ title: "邮件样张 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead"><div class="l-container l-container--narrow">
      <nav class="c-crumbs" aria-label="位置"><a href="/">首页</a><span class="c-crumbs__sep">/</span><a href="/_styleguide/">样张</a><span class="c-crumbs__sep">/</span><span>邮件</span></nav>
      <h1>邮件样张</h1><p class="c-pagehead__lede">网站发出的每一种邮件，用假数据渲染。主题前面实际还会加上后台设置的前缀。</p>
    </div></header>
    <div class="l-container l-container--narrow pt-10 pb-16 lg:pb-24">
      <nav class="mb-12 flex flex-wrap gap-x-6 gap-y-2" aria-label="邮件分类"><a v-for="(group,index) in groups" :key="group.name" :href="'#mail-' + (index + 1)" class="text-primary-text">{{ group.name }}（{{ group.items.length }}）</a></nav>
      <div class="flex flex-col gap-16">
        <section v-for="(group,index) in groups" :key="group.name" :aria-labelledby="'mail-' + (index + 1)" class="flex flex-col gap-12">
          <div class="c-sectionhead"><h2 :id="'mail-' + (index + 1)">{{ group.name }}</h2></div>
          <article v-for="sample in group.items" :key="sample.key" class="flex flex-col gap-3" :data-mail-sample="sample.key">
            <h3 class="text-lg font-semibold">{{ sample.title }}</h3>
            <dl class="c-facts c-panel"><dt>收件人</dt><dd>{{ sample.to }}</dd><dt>主题</dt><dd>{{ sample.subject }}</dd></dl>
            <iframe class="c-mailframe" :src="'/_styleguide/emails/' + sample.key + '/'" :title="sample.title + '的 HTML 版'" loading="lazy"></iframe>
            <details><summary class="cursor-pointer text-fg-2">纯文本版</summary><pre class="c-mailtext">{{ sample.text }}</pre></details>
          </article>
        </section>
      </div>
    </div>
  </main>
</template>
