<script setup lang="ts">
import { seatCells } from "@sjtu-ow/shared/display"
defineProps<{ taken: number; total: number; extra?: string }>()
</script>
<template>
  <span :class="['c-seats', extra]" role="img" :aria-label="`已报 ${taken ?? 0} 人，一场需要 ${total} 人`" data-seats><i v-for="(on, i) in seatCells(taken, total)" :key="i" v-bind="on ? { class: 'is-taken' } : {}"></i></span>
</template>
