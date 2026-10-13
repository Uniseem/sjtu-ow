<script setup lang="ts">
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import { formatContentTime } from "./types"
import { onMounted } from "vue"
import { useAdminApi } from "../../core/api"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import { useContentResource } from "./use-resource"
import { readSiteParts } from "./pending"
function truncateIntro(value: string): string {
  const chars = Array.from(value)
  return chars.length > 120 ? chars.slice(0, 119).join("") + "…" : value
}
const api = useAdminApi()
const resource = useContentResource((signal) => readSiteParts(api, { signal }))
onMounted(() => { void resource.load() })
</script>
<template>
  <AdminPage title="网站页面" section="content">
    <ContentLoad :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.load" />
    <template v-if="resource.data.value">
      <section class="b-section" data-site-part="pins">
        <div class="c-panel__head">
          <h2 class="b-section__title">首页的置顶文章 <span v-if="resource.data.value.home.has_unpublished_changes" class="b-sub" data-unpublished>有改动还没发布</span></h2>
          <RouterLink class="c-btn c-btn--secondary c-btn--sm" to="/admin/pages/pins/">改置顶</RouterLink>
        </div>
        <ol v-if="resource.data.value.pinned.length" class="b-list"><li v-for="(article, index) in resource.data.value.pinned" :key="article.id">{{ index + 1 }}. {{ article.title }}<span v-if="!article.live" class="b-sub">已撤下，首页不显示</span></li></ol>
        <p v-else class="b-section__text">没有置顶文章，首页按发布时间排。</p>
      </section>
      <section class="b-section" data-site-part="intro">
        <div class="c-panel__head">
          <h2 class="b-section__title">资讯栏目的介绍 <span v-if="resource.data.value.news.has_unpublished_changes" class="b-sub" data-unpublished>有改动还没发布</span></h2>
          <RouterLink class="c-btn c-btn--secondary c-btn--sm" to="/admin/pages/intro/">改介绍</RouterLink>
        </div>
        <p class="b-section__text">{{ truncateIntro(resource.data.value.news.intro_md) || '还没写介绍。' }}</p>
      </section>
      <section class="b-form" data-site-part="pages">
        <h2 class="b-section__title">页面</h2>
        <table v-if="resource.data.value.items.length" class="c-table c-table--stack">
          <thead><tr><th>页面</th><th>地址</th><th>状态</th><th>最后改动</th><th><span class="sr-only">操作</span></th></tr></thead>
          <tbody>
            <tr v-for="page in resource.data.value.items" :key="page.id">
              <td><RouterLink class="b-title" :to="`/admin/pages/${page.id}/`">{{ (page.draft_title ?? page.title) || '（无标题）' }}</RouterLink></td>
              <td data-label="地址"><span class="b-mono">/{{ page.slug }}/</span></td>
              <td data-label="状态"><CStatus :label="page.live ? page.has_unpublished_changes ? '已发布·有改动' : '已发布' : page.expired ? '已下线' : page.approved_schedule ? '定时上线' : '草稿'" :kind="page.live ? page.has_unpublished_changes ? 'warn' : 'ok' : page.expired ? 'off' : page.approved_schedule ? 'info' : 'done'" /></td>
              <td data-label="最后改动">{{ page.latest_revision_created_at ? formatContentTime(page.latest_revision_created_at) : '—' }}</td>
              <td><div class="b-rowacts"><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="`/admin/pages/${page.id}/`">编辑</RouterLink></div></td>
            </tr>
          </tbody>
        </table>
        <CEmpty v-else title="还没有页面" message="运行 init_site 建好关于我们和两份协议。" />
      </section>
    </template>
  </AdminPage>
</template>
