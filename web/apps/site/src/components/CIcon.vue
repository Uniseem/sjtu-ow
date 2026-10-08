<script setup lang="ts">
import { useAttrs } from "vue"
import { ICONS } from "../icons"

// The class falls through from the caller and replaces the default size
// (like icon.html's class param); inheritAttrs stays off so Vue does not
// append it next to the default.
defineOptions({ inheritAttrs: false })
defineProps<{ name: string }>()
const attrs = useAttrs()
</script>
<template>
  <svg
    :class="(attrs.class as string) ?? 'size-5'"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="1.75"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path v-for="d in ICONS[name]" :key="d" :d="d" />
  </svg>
</template>
