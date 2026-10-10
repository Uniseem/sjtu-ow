<script lang="ts">
export function load() { return { title: "找回密码" } }
</script>
<script setup lang="ts">
import { ref } from "vue"
import { useHead } from "@unhead/vue"
import { postApiAuthResetPassword } from "@sjtu-ow/api"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
import AuthError from "@sjtu-ow/ui/AuthError.vue"
import CField from "@sjtu-ow/ui/CField.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import { useApi } from "../api"
import { useViewer } from "../viewer"
import { finishAccountAction, useAccountForm } from "../account-form"
const viewer = useViewer()
const api = useApi()
const email = ref("")
const { pending, message, fields, submit } = useAccountForm()
useHead({ title: "找回密码 · SJTU-OW" })
function requestCode() {
  return submit(async () => {
    const result = await postApiAuthResetPassword(api, { email: email.value.trim() }, { unauthorized: "throw" })
    finishAccountAction("/accounts/password/reset/confirm/?" + new URLSearchParams({ email: result.email }))
  })
}
</script>
<template>
  <AuthLayout><h1>找回密码</h1>
    <div v-if="viewer.user" class="c-notice c-notice--info mt-6"><CIcon name="info" /><p class="c-notice__body">你已经以 {{ viewer.user.nickname }} 的身份登录。</p></div>
    <p>输入注册邮箱。无论该邮箱是否已注册，页面提示都相同。我们会发送 6 位验证码。</p>
    <form method="post" action="/accounts/password/reset/" :aria-busy="pending || undefined" @submit.prevent="requestCode">
      <AuthError :message="message" /><CField label="邮箱" input-id="id_email" required :errors="fields.email"><input id="id_email" v-model="email" type="email" name="email" autocomplete="email" placeholder="邮箱" maxlength="320" required></CField>
      <button type="submit" class="c-btn c-btn--primary" :disabled="pending">发送验证码</button>
    </form>
  </AuthLayout>
</template>
