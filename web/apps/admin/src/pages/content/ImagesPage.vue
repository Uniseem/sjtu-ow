<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiAdminImages, getApiAdminImageCollections } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminSession } from "../../core/session"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import ContentPager from "../../components/content/ContentPager.vue"
import ImageGrid from "../../components/content/ImageGrid.vue"
import { useContentResource } from "./use-resource"
import { positiveID } from "./types"

const api = useAdminApi()
const { user } = useAdminSession()
const route = useRoute()
const router = useRouter()
const query = ref(String(route.query.q ?? ""))
const collection = ref(String(route.query.collection ?? ""))
const canUpload = computed(() => Boolean(user.value?.superuser || user.value?.caps.includes("images.contribute")))
const resource = useContentResource((signal) => getApiAdminImages(api, {
  q: String(route.query.q ?? "").slice(0, 50),
  collection_id: positiveID(route.query.collection) ?? undefined,
  page: positiveID(route.query.page) ?? 1,
  page_size: 48,
}, { signal }))
const collections = useContentResource((signal) => getApiAdminImageCollections(api, { signal }))

function filter(): void {
  void router.push({
    path: route.path,
    query: {
      ...(query.value.trim() ? { q: query.value.trim().slice(0, 50) } : {}),
      ...(collection.value ? { collection: collection.value } : {}),
    },
  })
}
watch(() => route.fullPath, () => {
  query.value = String(route.query.q ?? "")
  collection.value = String(route.query.collection ?? "")
  void resource.load()
})
onMounted(() => { void resource.load(); void collections.load() })
</script>
<template>
  <AdminPage title="图片" section="content">
    <template #actions>
      <RouterLink v-if="user?.superuser" class="c-btn c-btn--secondary c-btn--sm" to="/admin/images/collections/">集合</RouterLink>
      <RouterLink v-if="canUpload" class="c-btn c-btn--primary c-btn--sm" to="/admin/images/upload/">上传图片</RouterLink>
    </template>
    <form class="b-filters" role="search" @submit.prevent="filter">
      <input v-model="query" type="search" name="q" class="c-input" maxlength="50" placeholder="搜标题" aria-label="搜标题">
      <select v-model="collection" class="c-input" name="collection" aria-label="集合" @change="filter">
        <option value="">全部集合</option>
        <option v-for="item in collections.data.value?.collections ?? []" :key="item.id" :value="String(item.id)">{{ item.name }}</option>
      </select>
      <button class="c-btn c-btn--secondary c-btn--sm">筛选</button>
      <span v-if="resource.data.value" class="b-count">{{ resource.data.value.total }} 张</span>
    </form>
    <ContentLoad :pending="collections.pending.value" :message="collections.message.value" :status="collections.status.value" @retry="collections.load" />
    <ContentLoad :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.load" />
    <template v-if="resource.data.value">
      <ImageGrid :images="resource.data.value.items" :collections="collections.data.value?.collections" />
      <section v-if="!resource.data.value.items.length" class="c-empty">
        <h2 class="c-empty__title">没有图片</h2>
        <p>换个筛选条件，或者上传几张。</p>
      </section>
      <ContentPager :page="resource.data.value.page" :total="resource.data.value.total" :page-size="resource.data.value.page_size" :pending="resource.pending.value" />
    </template>
  </AdminPage>
</template>
