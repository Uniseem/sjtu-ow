<script lang="ts">
import type { LoadCtx } from "../router"
export function load(ctx: LoadCtx) { const inactive = ctx.url.split('?')[0] === '/accounts/inactive/'; return { title: inactive ? '账号已停用' : '密码已更新', inactive } }
</script>
<script setup lang="ts">
import { computed, inject } from "vue"
import { useHead } from "@unhead/vue"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
const data = inject<{ title: string; inactive: boolean }>("page-data")
const inactive = computed(() => data?.inactive ?? true)
useHead(() => ({ title: (data?.title ?? '账号已停用') + ' · SJTU-OW' }))
</script>
<template><AuthLayout><template v-if="inactive"><h1>账号已停用</h1><p>这个账号目前不能登录。如有疑问请联系管理员。</p></template><template v-else><h1>密码已更新</h1><p>你的密码已经改好，现在可以使用新密码登录。</p><a href="/accounts/login/" class="c-btn c-btn--primary">去登录</a></template></AuthLayout></template>
