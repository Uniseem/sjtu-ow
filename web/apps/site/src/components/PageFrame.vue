<script setup lang="ts">
import { inject, provide, toRaw } from "vue"
import type { PageData } from "../router"

// The loader commits the next payload before the router unmounts this page.
// Keep each mounted page's payload together until its route is replaced.
// The full-path key also replaces the scope when only a filter changes.
const payload = inject<PageData>("page-data")
if (!payload) throw new Error("Missing page payload")
provide("page-data", { ...toRaw(payload) })
</script>
<template><slot /></template>
