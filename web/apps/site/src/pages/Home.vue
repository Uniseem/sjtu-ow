<script lang="ts">
export function load() {
  // marker 里的 < 走真渲染，确认状态脚本把 < 转义了。页面上不显示。
  return { title: "SJTU-OW", marker: "<" }
}
</script>
<script setup lang="ts">
import { inject } from "vue"
import { useHead } from "@unhead/vue"

const data = inject<{ title: string }>("page-data")
useHead({ title: data?.title ?? "SJTU-OW" })
</script>
<template>
  <main id="main" class="flex-1">
    <h1>{{ data?.title }}</h1>
  </main>
</template>
