<script setup lang="ts">
import CIcon from "./CIcon.vue"
withDefaults(defineProps<{ page: number; pages: number; extraQuery?: string }>(), { extraQuery: "" })
function href(n: number, query: string): string {
  const params = new URLSearchParams(query)
  params.delete("page")
  const extra = params.toString()
  return `?${extra ? extra + "&" : ""}page=${n}`
}
</script>
<template>
  <nav v-if="pages > 1" class="c-pager" aria-label="分页">
    <a v-if="page > 1" class="c-btn c-btn--secondary c-btn--sm" :href="href(page - 1, extraQuery)" rel="prev"><CIcon name="arrow-left" />上一页</a>
    <span v-else class="c-btn c-btn--secondary c-btn--sm" aria-disabled="true"><CIcon name="arrow-left" />上一页</span>
    <span class="c-pager__pos"><strong>{{ page }}</strong> / {{ pages }}</span>
    <a v-if="page < pages" class="c-btn c-btn--secondary c-btn--sm" :href="href(page + 1, extraQuery)" rel="next">下一页<CIcon name="arrow-right" /></a>
    <span v-else class="c-btn c-btn--secondary c-btn--sm" aria-disabled="true">下一页<CIcon name="arrow-right" /></span>
  </nav>
</template>
