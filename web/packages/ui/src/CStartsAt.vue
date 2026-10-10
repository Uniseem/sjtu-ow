<script setup lang="ts">
import { owDate, owTime } from "@sjtu-ow/shared/time"
defineProps<{ startsAt?: string | null }>()
</script>
<template><template v-if="startsAt">{{ owDate(new Date(startsAt)) }} {{ owTime(new Date(startsAt)) }}</template><span v-else class="text-fg-3">未定</span></template>
