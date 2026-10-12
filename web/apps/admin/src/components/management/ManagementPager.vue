<script setup lang="ts">
import { computed } from "vue"
import { useRoute } from "vue-router"
import CPager from "@sjtu-ow/ui/CPager.vue"
const props = defineProps<{ total: number; page: number; size: number }>()
const route = useRoute()
const pages = computed(() => Math.max(1, Math.ceil(props.total / Math.max(1, props.size))))
const query = computed(() => {
  const params = new URLSearchParams()
  for (const [key,value] of Object.entries(route.query)) {
    if (key === "page" || value === null || value === undefined) continue
    for (const part of Array.isArray(value) ? value : [value]) if (part !== null) params.append(key,part)
  }
  return params.toString()
})
</script>
<template><CPager :page="page" :pages="pages" :extra-query="query" /></template>
