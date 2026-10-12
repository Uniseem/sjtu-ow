<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiAuthResetPasswordCodeState } from "@sjtu-ow/api"
import { PageRedirect } from "@sjtu-ow/shared/navigation"
export async function load(ctx: LoadCtx) {
  const state = await getApiAuthResetPasswordCodeState(ctx.api)
  if (!state.active || !state.email) throw new PageRedirect("/accounts/login/")
  const email = state.email
  return { title: "找回密码", email }
}
</script>
<script setup lang="ts">
import { computed, inject, ref } from "vue"
import { useHead } from "@unhead/vue"
import { postApiAuthResetPasswordVerify, ApiError } from "@sjtu-ow/api"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
import AuthError from "@sjtu-ow/ui/AuthError.vue"
import CField from "@sjtu-ow/ui/CField.vue"
import { useApi } from "../api"
import { finishAccountAction, useAccountForm } from "../account-form"
const data = inject<{ email: string }>("page-data")
const email = computed(() => data?.email ?? "")
const api = useApi()
const code = ref("")
const { pending, message, fields, submit } = useAccountForm()
useHead({ title: "找回密码 · SJTU-OW" })
function confirmCode() {
  return submit(async () => {
    try {
      await postApiAuthResetPasswordVerify(api, { email: email.value, code: code.value.trim() }, { unauthorized: "throw" })
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        const state = await getApiAuthResetPasswordCodeState(api)
        if (!state.active) { finishAccountAction("/accounts/login/"); return }
      }
      throw error
    }
    finishAccountAction("/accounts/password/reset/complete/")
  })
}
</script>
<template>
  <AuthLayout><h1>输入找回密码验证码</h1><p>验证码已发送到 <a :href="'mailto:' + email" class="c-link">{{ email }}</a>。</p>
    <form method="post" action="/accounts/password/reset/confirm/" :aria-busy="pending || undefined" @submit.prevent="confirmCode">
      <AuthError :message="message" /><CField label="验证码" input-id="id_code" required :errors="fields.code"><input id="id_code" v-model="code" type="text" name="code" placeholder="验证码" autocomplete="one-time-code" required></CField>
      <button type="submit" class="c-btn c-btn--primary" :disabled="pending">确认</button>
    </form>
  </AuthLayout>
</template>
