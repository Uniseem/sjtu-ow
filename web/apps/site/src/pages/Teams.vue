<script lang="ts">
export function load() {
  return { title: "战队" }
}
</script>
<script setup lang="ts">
import { inject } from "vue"
import { useHead } from "@unhead/vue"

const data = inject<{ title: string }>("page-data")
useHead({ title: data?.title ?? "战队" })
</script>
<template>
  <main id="main" class="flex-1">
    <h1>{{ data?.title }}</h1>
  </main>
</template>
