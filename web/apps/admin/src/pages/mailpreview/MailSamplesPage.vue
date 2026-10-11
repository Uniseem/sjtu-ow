<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useAdminApi } from "../../core/api"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import { useContentResource } from "../content/use-resource"
import { getMailSamples } from "./pending"
import MailSampleCard from "./MailSampleCard.vue"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const group = ref(String(route.query.group ?? ""))
const query = ref(String(route.query.q ?? ""))
const resource = useContentResource((signal) => getMailSamples(api, {
  group: String(route.query.group ?? ""),
  q: String(route.query.q ?? "").slice(0, 50),
}, { signal }))
const grouped = computed(() => {
  const catalogue = resource.data.value
  if (!catalogue) return []
  return catalogue.groups.map((group) => ({
    name: group.name,
    items: catalogue.items.filter((item) => item.group === group.name),
  })).filter((group) => group.items.length > 0)
})
function filter(): void {
  void router.push({ path: route.path, query: {
    ...(group.value ? { group: group.value } : {}),
    ...(query.value.trim() ? { q: query.value.trim().slice(0, 50) } : {}),
  } })
}
watch(() => route.fullPath, () => {
  group.value = String(route.query.group ?? "")
  query.value = String(route.query.q ?? "")
  void resource.load()
})
onMounted(() => { void resource.load() })
</script>
<template>
  <AdminPage title="邮件样张" section="settings">
    <p class="b-section__text">网站发出的每一种邮件，用固定假数据渲染。样张只用于检查排版，不会发送邮件。主题前面实际还会加上后台设置的前缀。</p>
    <form class="b-filters" role="search" @submit.prevent="filter">
      <input v-model="query" name="q" type="search" class="c-input" maxlength="50" placeholder="搜索邮件样张" aria-label="搜索邮件样张">
      <select v-model="group" name="group" class="c-input" aria-label="邮件分类" @change="filter">
        <option value="">全部分类</option>
        <option v-for="item in resource.data.value?.groups ?? []" :key="item.name" :value="item.name">{{ item.name }}（{{ item.count }}）</option>
      </select>
      <button class="c-btn c-btn--secondary c-btn--sm" :disabled="resource.pending.value">筛选</button>
    </form>
    <ContentLoad :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.load" />
    <template v-if="resource.data.value">
      <nav class="mb-12 flex flex-wrap gap-x-6 gap-y-2" aria-label="邮件分类">
        <a v-for="(group, index) in grouped" :key="group.name" :href="`#mail-${index + 1}`" class="text-primary-text">{{ group.name }}（{{ group.items.length }}）</a>
      </nav>
      <div class="flex flex-col gap-16">
        <section v-for="(group, index) in grouped" :key="group.name" :aria-labelledby="`mail-${index + 1}`" class="flex flex-col gap-12">
          <div class="c-sectionhead"><h2 :id="`mail-${index + 1}`">{{ group.name }}</h2></div>
          <MailSampleCard v-for="sample in group.items" :key="sample.key" :sample="sample" />
        </section>
      </div>
      <section v-if="!resource.data.value.items.length" class="c-empty"><h2 class="c-empty__title">没有邮件样张</h2><p>换个搜索词或分类试试。</p></section>
      <p class="b-sub">共 {{ resource.data.value.total }} 种样张；全部使用虚构身份、固定日期和示例地址。</p>
    </template>
  </AdminPage>
</template>
