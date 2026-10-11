<script setup lang="ts">
import { computed } from "vue"
import { useRoute } from "vue-router"
const props = defineProps<{ total: number; page: number; size: number }>()
const route = useRoute()
const pages = computed(() => Math.max(1, Math.ceil(props.total / Math.max(1, props.size))))
function href(page: number) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(route.query)) {
    if (key === "page" || value === null || value === undefined) continue
    if (Array.isArray(value)) value.forEach(part => { if (part !== null) query.append(key, part) })
    else query.set(key, value)
  }
  if (page > 1) query.set("page", String(page))
  const suffix = query.toString()
  return route.path + (suffix ? "?" + suffix : "")
}
</script>
<template>
  <nav v-if="pages > 1" class="c-pager" aria-label="分页">
    <RouterLink v-if="page > 1" class="c-btn c-btn--quiet c-btn--sm" :to="href(page - 1)">上一页</RouterLink>
    <span class="b-sub">第 {{ page }} / {{ pages }} 页，共 {{ total }} 条</span>
    <RouterLink v-if="page < pages" class="c-btn c-btn--quiet c-btn--sm" :to="href(page + 1)">下一页</RouterLink>
  </nav>
</template>
