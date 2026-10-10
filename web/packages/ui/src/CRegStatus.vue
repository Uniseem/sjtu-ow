<script setup lang="ts">
import CStatus from "./CStatus.vue"
defineProps<{ status: string; label: string }>()
const kinds: Record<string, string> = { approved: "ok", pending: "warn", rejected: "rejected" }
</script>
<template><CStatus :kind="kinds[status] ?? 'off'" :label="label" /></template>
