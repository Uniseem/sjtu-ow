<script setup lang="ts">
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import type { RouteLocationRaw } from "vue-router"
defineProps<{
  page: number
  pages: number
  previous: RouteLocationRaw
  next: RouteLocationRaw
}>()
</script>

<template>
  <nav v-if="pages > 1" class="c-pager" aria-label="分页">
    <RouterLink v-if="page > 1" class="c-btn c-btn--secondary c-btn--sm" :to="previous" rel="prev"><CIcon name="arrow-left" />上一页</RouterLink>
    <span v-else class="c-btn c-btn--secondary c-btn--sm" aria-disabled="true"><CIcon name="arrow-left" />上一页</span>
    <span class="c-pager__pos"><strong>{{ page }}</strong> / {{ pages }}</span>
    <RouterLink v-if="page < pages" class="c-btn c-btn--secondary c-btn--sm" :to="next" rel="next">下一页<CIcon name="arrow-right" /></RouterLink>
    <span v-else class="c-btn c-btn--secondary c-btn--sm" aria-disabled="true">下一页<CIcon name="arrow-right" /></span>
  </nav>
</template>
