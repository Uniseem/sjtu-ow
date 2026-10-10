<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiAuthEmailState } from "@sjtu-ow/api"
export async function load(ctx: LoadCtx) {
  const state = await getApiAuthEmailState(ctx.api)
  return { title: "修改邮箱", state, draft: ctx.query.draft ?? "" }
}
</script>
<script setup lang="ts">
import { inject, ref } from "vue"
import { useHead } from "@unhead/vue"
import { postApiAuthEmailChange, deleteApiAuthEmailChange, ApiError } from "@sjtu-ow/api"
import type { GetApiAuthEmailStateOut } from "@sjtu-ow/api"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
import AuthBack from "@sjtu-ow/ui/AuthBack.vue"
import AuthError from "@sjtu-ow/ui/AuthError.vue"
import CField from "@sjtu-ow/ui/CField.vue"
import { useApi } from "../api"
import { finishAccountAction, useAccountForm, useCodeCooldown } from "../account-form"
const data = inject<{ state: GetApiAuthEmailStateOut; draft: string }>("page-data")
const state = ref(data?.state)
const email = ref(data?.draft ?? "")
const api = useApi()
const { pending, message, fields, submit } = useAccountForm()
const { seconds, start } = useCodeCooldown()
useHead({ title: "修改邮箱 · SJTU-OW" })
function request(target: string) {
  const reauth = () => finishAccountAction("/accounts/reauthenticate/?next=" + encodeURIComponent("/accounts/email/?draft=" + encodeURIComponent(target)))
  if (!state.value?.reauthenticated) { reauth(); return }
  return submit(async () => {
    try { await postApiAuthEmailChange(api, { new_email: target }, { unauthorized: "throw" }) }
    catch (error) {
      if (error instanceof ApiError && error.code === "reauth_required") reauth()
      if (error instanceof ApiError && error.status === 429) start()
      throw error
    }
    finishAccountAction("/accounts/confirm-email/?mode=change&email=" + encodeURIComponent(target))
  })
}
function resend() { if (!seconds.value && !pending.value && state.value?.pending_email) return request(state.value.pending_email) }
function cancel() {
  return submit(async () => { await deleteApiAuthEmailChange(api); if (state.value) state.value.pending_email = undefined })
}
</script>
<template>
  <AuthLayout><AuthBack here="修改邮箱" /><h1>修改邮箱</h1>
    <CField v-if="state?.email" label="当前邮箱" input-id="current_email" class="mt-7"><input id="current_email" type="email" :value="state.email" disabled></CField>
    <template v-if="state?.pending_email">
      <CField label="正在改为" input-id="new_email" class="mt-5" help="新邮箱尚未验证。验证通过后才会替换。"><input id="new_email" type="email" :value="state.pending_email" disabled></CField>
      <form id="pending-email" method="post" action="/accounts/email/" class="!mt-3 !flex-row flex-wrap" @submit.prevent="resend"><input type="hidden" name="email" :value="state.pending_email"><button type="submit" name="action_send" class="c-btn c-btn--secondary c-btn--sm" :disabled="pending || seconds > 0">{{ seconds ? seconds + ' 秒后可重发' : '重发验证码' }}</button><button type="button" name="action_remove" class="c-btn c-btn--quiet c-btn--sm" :disabled="pending" @click="cancel">取消修改</button></form>
    </template>
    <form method="post" action="/accounts/email/" :aria-busy="pending || undefined" @submit.prevent="request(email.trim())"><AuthError :message="message" /><CField label="邮箱" input-id="id_email" required :errors="fields.new_email"><input id="id_email" v-model="email" type="email" name="email" autocomplete="email" placeholder="邮箱" required></CField><div><button type="submit" name="action_add" class="c-btn c-btn--primary" :disabled="pending">更换邮箱</button></div></form>
  </AuthLayout>
</template>
