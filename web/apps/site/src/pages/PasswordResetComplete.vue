<script lang="ts">
import type { LoadCtx } from "../router"
import { PageRedirect } from "@sjtu-ow/shared/navigation"
import { getApiAuthResetPasswordState } from "@sjtu-ow/api"
export async function load(ctx: LoadCtx) {
  const state = await getApiAuthResetPasswordState(ctx.api)
  if (!state.verified) throw new PageRedirect("/accounts/password/reset/confirm/")
  return { title: "设置新密码" }
}
</script>
<script setup lang="ts">
import { ref } from "vue"
import { useHead } from "@unhead/vue"
import { postApiAuthResetPasswordComplete, ApiError } from "@sjtu-ow/api"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
import AuthError from "@sjtu-ow/ui/AuthError.vue"
import AuthNewPasswords from "@sjtu-ow/ui/AuthNewPasswords.vue"
import { useApi } from "../api"
import { finishAccountAction, useAccountForm } from "../account-form"
const api = useApi()
const password = ref("")
const confirmation = ref("")
const expired = ref(false)
const { pending, message, fields, submit } = useAccountForm()
useHead({ title: "设置新密码 · SJTU-OW" })
function complete() {
  return submit(async () => {
    try { await postApiAuthResetPasswordComplete(api, { password: password.value, confirm_password: confirmation.value }, { unauthorized: "throw" }) }
    catch (error) { if (error instanceof ApiError && error.fields?.code) expired.value = true; throw error }
    finishAccountAction("/accounts/password/reset/done/")
  })
}
</script>
<template>
  <AuthLayout><h1>设置新密码</h1>
    <p v-if="expired">重置链接无效或已使用。请 <a href="/accounts/password/reset/" class="c-link">重新申请</a>。</p>
    <form v-else method="post" action="/accounts/password/reset/complete/" :aria-busy="pending || undefined" @submit.prevent="complete"><AuthError :message="message" /><AuthNewPasswords v-model:password="password" v-model:confirmation="confirmation" :errors="fields" /><button type="submit" class="c-btn c-btn--primary" :disabled="pending">保存新密码</button></form>
  </AuthLayout>
</template>
