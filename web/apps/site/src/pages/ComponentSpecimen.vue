<script setup lang="ts">
import { useHead } from "@unhead/vue"
import ComponentSamples from "../components/ComponentSamples.vue"
import { inject } from "vue"
import type { PageData } from "../router"
const data = inject<PageData>("page-data")
useHead({ title: "组件样张 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })
</script>
<template><main id="main" class="l-container l-section"><h1>组件样张</h1><ComponentSamples :image-id="typeof data?.imageId === 'number' ? data.imageId : undefined" /></main></template>
