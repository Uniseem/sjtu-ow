<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue"
import { useAdminApi } from "../../core/api"
import { listContentArticles } from "../../pages/content/pending"
import { useContentResource } from "../../pages/content/use-resource"
import type { Article } from "../../pages/content/types"
import ContentLoad from "./ContentLoad.vue"
const props = withDefaults(defineProps<{ excluded?: number[] }>(), { excluded: () => [] })
const emit = defineEmits<{ select: [article: Article]; close: [] }>()
const api = useAdminApi()
const dialog = ref<HTMLDialogElement | null>(null)
const query = ref("")
const submitted = ref("")
const page = ref(1)
const resource = useContentResource((signal) => listContentArticles(api, {
  q: submitted.value,
  status: "live",
  page: page.value,
  page_size: 25,
}, { signal }))
const rows = computed(() => (resource.data.value?.items ?? []).filter((article): article is Article => article !== null && article.live))
const pages = computed(() => Math.max(1, Math.ceil((resource.data.value?.total ?? 0) / 25)))
let oldFocus: HTMLElement | null = null
function filter(): void {
  submitted.value = query.value.trim().slice(0, 50)
  page.value = 1
  void resource.load()
}
function go(value: number): void {
  if (value < 1 || value > pages.value || resource.pending.value) return
  page.value = value
  void resource.load()
}
function cancel(event: Event): void { event.preventDefault(); emit("close") }
onMounted(async () => {
  oldFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  await nextTick()
  dialog.value?.showModal()
  dialog.value?.querySelector<HTMLInputElement>("input")?.focus()
  void resource.load()
})
onBeforeUnmount(() => { dialog.value?.close(); oldFocus?.focus() })
</script>
<template>
  <dialog ref="dialog" class="b-dialog" aria-labelledby="article-chooser-title" @cancel="cancel">
    <div class="c-panel__head"><h2 id="article-chooser-title" class="b-section__title">选择已发布的文章</h2><button type="button" class="c-btn c-btn--quiet c-btn--sm" @click="$emit('close')">关闭</button></div>
    <form class="b-filters" role="search" @submit.prevent="filter">
      <input v-model="query" class="c-input" type="search" maxlength="50" placeholder="搜标题" aria-label="搜标题">
      <button class="c-btn c-btn--secondary c-btn--sm" :disabled="resource.pending.value">筛选</button>
    </form>
    <ContentLoad :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.load" />
    <table v-if="rows.length" class="c-table c-table--stack">
      <thead><tr><th>文章</th><th>分类</th><th>作者</th><th><span class="sr-only">操作</span></th></tr></thead>
      <tbody>
        <tr v-for="article in rows" :key="article.id">
          <td>{{ article.title }}</td>
          <td data-label="分类">{{ article.category_name }}</td>
          <td data-label="作者">{{ article.author_name }}</td>
          <td><button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="props.excluded.includes(article.id)" @click="$emit('select', article)">{{ props.excluded.includes(article.id) ? '已选择' : '选择' }}</button></td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="resource.data.value" class="b-section__text">没有可选的已发布文章。</p>
    <nav v-if="pages > 1" class="c-pager" aria-label="文章分页">
      <button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="page <= 1 || resource.pending.value" @click="go(page - 1)">上一页</button>
      <span class="c-pager__pos"><strong>{{ page }}</strong> / {{ pages }}</span>
      <button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="page >= pages || resource.pending.value" @click="go(page + 1)">下一页</button>
    </nav>
  </dialog>
</template>
