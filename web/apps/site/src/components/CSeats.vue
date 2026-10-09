<script setup lang="ts">
defineProps<{ taken: number; total: number; extra?: string }>()
</script>
<template>
  <span
    :class="['c-seats', extra]"
    role="img"
    :aria-label="`已报 ${taken ?? 0} 人，一场需要 ${total} 人`"
    data-seats
  >
    <i v-for="i in total" :key="i" :class="{ 'is-taken': i <= taken }"></i>
  </span>
</template>
