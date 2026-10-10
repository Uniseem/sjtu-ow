<script setup lang="ts">
withDefaults(defineProps<{ kind?: string; label: string }>(), { kind: "done" })
const aliases: Record<string, string> = { success: "ok", warning: "warn", error: "rejected", neutral: "done", primary: "live" }
</script>
<template><span :class="`c-status c-status--${aliases[kind] ?? kind}`">{{ label }}</span></template>
