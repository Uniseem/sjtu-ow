<script lang="ts">
import type { LoadCtx } from "../router"
import { PageRedirect, safeNext } from "@sjtu-ow/shared/navigation"
export function load(ctx: LoadCtx) {
  const email = ctx.query.email?.trim()
  if (!email) throw new PageRedirect("/accounts/login/")
  return { title: "邮箱验证", email, next: safeNext(ctx.query.next, "/me/"), welcome: ctx.query.welcome === "1" }
}
</script>
<script setup lang="ts">
import { computed, inject, ref } from "vue"
import { useHead } from "@unhead/vue"
import { postApiAuthVerifyEmail, postApiAuthResendCode, postApiAuthLogout, ApiError } from "@sjtu-ow/api"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
import AuthError from "@sjtu-ow/ui/AuthError.vue"
import CField from "@sjtu-ow/ui/CField.vue"
import { useApi } from "../api"
import { useViewer } from "../viewer"
import { finishAccountAction, useAccountForm, useCodeCooldown } from "../account-form"
const data = inject<{ email: string; next: string; welcome: boolean }>("page-data")
const email = computed(() => data?.email ?? "")
const api = useApi()
const viewer = useViewer()
const code = ref("")
const sent = ref(false)
const { pending, message, fields, submit } = useAccountForm()
const { seconds, start } = useCodeCooldown()
useHead({ title: "邮箱验证 · SJTU-OW" })
function verify() {
  return submit(async () => {
    await postApiAuthVerifyEmail(api, { email: email.value, code: code.value.trim() }, { unauthorized: "throw" })
    finishAccountAction(safeNext(data?.next, "/me/"))
  })
}
function resend() {
  if (seconds.value || pending.value) return
  return submit(async () => {
    try {
      await postApiAuthResendCode(api, { email: email.value }, { unauthorized: "throw" })
      sent.value = true
      start()
    } catch (error) {
      if (error instanceof ApiError && error.status === 429) start()
      throw error
    }
  })
}
function cancel() { return submit(async () => { if (viewer.user) await postApiAuthLogout(api); finishAccountAction("/accounts/login/") }) }
</script>
<template>
  <AuthLayout>
    <h1>输入邮箱验证码</h1><p>验证码已发送到 <a :href="'mailto:' + email" class="c-link">{{ email }}</a>，有效期较短，请尽快输入。</p>
    <form method="post" action="/accounts/confirm-email/" :aria-busy="pending || undefined" @submit.prevent="verify">
      <AuthError :message="message" />
      <CField label="验证码" input-id="id_code" required :errors="fields.code"><input id="id_code" v-model="code" type="text" name="code" placeholder="验证码" autocomplete="one-time-code" required></CField>
      <input v-if="data?.next" type="hidden" name="next" :value="data.next">
      <button type="submit" class="c-btn c-btn--primary" :disabled="pending">确认</button>
    </form>
    <form method="post" action="/accounts/confirm-email/" @submit.prevent="resend"><input type="hidden" name="action" value="resend"><button type="submit" class="c-btn c-btn--quiet" :disabled="pending || seconds > 0">{{ seconds ? seconds + ' 秒后可重新发送' : '重新发送验证码' }}</button></form>
    <p v-if="sent" role="status" class="text-sm text-fg-2">验证码已重新发送，请检查邮箱。</p>
    <form method="post" action="/accounts/logout/" @submit.prevent="cancel"><input type="hidden" name="next" value="/accounts/login/"><button type="submit" class="c-btn c-btn--quiet" :disabled="pending">取消</button></form>
  </AuthLayout>
</template>
