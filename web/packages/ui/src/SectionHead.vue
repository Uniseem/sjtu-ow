<script setup lang="ts">
import CIcon from "./CIcon.vue"

defineProps<{ title: string; headingId?: string; moreHref?: string; moreLabel?: string }>()
</script>
<template>
  <div class="c-sectionhead">
    <h2 :id="headingId">{{ title }}</h2>
    <a v-if="moreHref" :href="moreHref" class="c-btn c-btn--quiet">{{ moreLabel ?? "全部" }}<CIcon name="arrow-right" /></a>
  </div>
</template>
