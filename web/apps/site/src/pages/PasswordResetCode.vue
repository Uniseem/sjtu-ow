<script lang="ts">
import type { LoadCtx } from "../router"
import { PageRedirect } from "@sjtu-ow/shared/navigation"
export function load(ctx: LoadCtx) {
  const email = ctx.query.email?.trim()
  if (!email) throw new PageRedirect("/accounts/password/reset/")
  return { title: "找回密码", email }
}
</script>
<script setup lang="ts">
import { computed, inject, ref } from "vue"
import { useHead } from "@unhead/vue"
import { postApiAuthResetPasswordVerify, postApiAuthResetPassword } from "@sjtu-ow/api"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
import AuthError from "@sjtu-ow/ui/AuthError.vue"
import CField from "@sjtu-ow/ui/CField.vue"
import { useApi } from "../api"
import { finishAccountAction, useAccountForm, useCodeCooldown } from "../account-form"
const data = inject<{ email: string }>("page-data")
const email = computed(() => data?.email ?? "")
const api = useApi()
const code = ref("")
const sent = ref(false)
const { pending, message, fields, submit } = useAccountForm()
const { seconds, start } = useCodeCooldown()
useHead({ title: "找回密码 · SJTU-OW" })
function confirmCode() {
  return submit(async () => {
    await postApiAuthResetPasswordVerify(api, { email: email.value, code: code.value.trim() }, { unauthorized: "throw" })
    finishAccountAction("/accounts/password/reset/complete/")
  })
}
function resend() {
  if (pending.value || seconds.value) return
  return submit(async () => { await postApiAuthResetPassword(api, { email: email.value }, { unauthorized: "throw" }); sent.value = true; start() })
}
</script>
<template>
  <AuthLayout><h1>输入找回密码验证码</h1><p>验证码已发送到 <a :href="'mailto:' + email" class="c-link">{{ email }}</a>。</p>
    <form method="post" action="/accounts/password/reset/confirm/" :aria-busy="pending || undefined" @submit.prevent="confirmCode">
      <AuthError :message="message" /><CField label="验证码" input-id="id_code" required :errors="fields.code"><input id="id_code" v-model="code" type="text" name="code" placeholder="验证码" autocomplete="one-time-code" required></CField>
      <button type="submit" class="c-btn c-btn--primary" :disabled="pending">确认</button>
    </form>
    <form method="post" action="/accounts/password/reset/confirm/" @submit.prevent="resend"><input type="hidden" name="action" value="resend"><button type="submit" class="c-btn c-btn--quiet" :disabled="pending || seconds > 0">{{ seconds ? seconds + ' 秒后可重新发送' : '重新发送验证码' }}</button></form>
    <p v-if="sent" class="text-sm text-fg-2" role="status">验证码已重新发送，请检查邮箱。</p>
  </AuthLayout>
</template>
