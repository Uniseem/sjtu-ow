<script setup lang="ts">
defineProps<{ here: string }>()
</script>
<template><nav class="c-crumbs mb-6" aria-label="位置"><a href="/">首页</a><span class="c-crumbs__sep">/</span><a href="/me/">个人中心</a><span class="c-crumbs__sep">/</span><a href="/me/security/">账号安全</a><span class="c-crumbs__sep">/</span><span>{{ here }}</span></nav></template>
