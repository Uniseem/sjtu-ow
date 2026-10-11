<script setup lang="ts">
import type { AdminFailure } from "../core/error"
defineProps<{ failure: AdminFailure; loginHref: string }>()
const emit = defineEmits<{ retry: [] }>()
</script>
<template>
  <main id="main" class="b-main"><section class="c-panel" role="alert"><h1>{{ failure.title }}</h1><p class="mt-3">{{ failure.message }}</p><div class="c-formbar"><a v-if="failure.status === 401" :href="loginHref" class="c-btn c-btn--primary">重新登录</a><button v-if="failure.retry" type="button" class="c-btn c-btn--primary" @click="emit('retry')">重新打开</button><a href="/admin/" class="c-btn c-btn--secondary">后台首页</a></div></section></main>
</template>
