<script setup lang="ts">
import { computed } from "vue"
import { useRoute, useRouter } from "vue-router"
const props = defineProps<{ page: number; total: number; pageSize: number; pending?: boolean }>()
const route = useRoute()
const router = useRouter()
const pages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
function go(page: number): void {
  if (props.pending || page < 1 || page > pages.value) return
  void router.push({ path: route.path, query: { ...route.query, page: String(page) } })
}
</script>
<template>
  <nav v-if="pages > 1" class="c-pager" aria-label="分页">
    <button class="c-btn c-btn--secondary c-btn--sm" :disabled="pending || page <= 1" @click="go(page - 1)">上一页</button>
    <span class="c-pager__pos"><strong>{{ page }}</strong> / {{ pages }}</span>
    <button class="c-btn c-btn--secondary c-btn--sm" :disabled="pending || page >= pages" @click="go(page + 1)">下一页</button>
  </nav>
</template>
