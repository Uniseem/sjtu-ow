<script lang="ts">
export function load() { return { title: "修改密码" } }
</script>
<script setup lang="ts">
import { ref } from "vue"
import { useHead } from "@unhead/vue"
import { postApiAuthChangePassword } from "@sjtu-ow/api"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
import AuthBack from "@sjtu-ow/ui/AuthBack.vue"
import AuthError from "@sjtu-ow/ui/AuthError.vue"
import AuthNewPasswords from "@sjtu-ow/ui/AuthNewPasswords.vue"
import CField from "@sjtu-ow/ui/CField.vue"
import { useApi } from "../api"
import { finishAccountAction, useAccountForm } from "../account-form"
const api = useApi()
const oldPassword = ref("")
const password = ref("")
const confirmation = ref("")
const { pending, message, fields, submit } = useAccountForm()
useHead({ title: "修改密码 · SJTU-OW" })
function change() {
  return submit(async () => {
    await postApiAuthChangePassword(api, { old_password: oldPassword.value, password: password.value, confirm_password: confirmation.value })
    finishAccountAction("/accounts/password/change/")
  })
}
</script>
<template>
  <AuthLayout><AuthBack here="修改密码" /><h1>修改密码</h1>
    <form method="post" action="/accounts/password/change/" :aria-busy="pending || undefined" @submit.prevent="change">
      <AuthError :message="message" />
      <CField label="当前密码" input-id="id_oldpassword" required :errors="fields.old_password"><input id="id_oldpassword" v-model="oldPassword" type="password" name="oldpassword" placeholder="当前密码" autocomplete="current-password" required aria-describedby="id_oldpassword_helptext"><template #help><a id="id_oldpassword_helptext" href="/accounts/password/reset/">忘记密码？</a></template></CField>
      <AuthNewPasswords v-model:password="password" v-model:confirmation="confirmation" :errors="fields" />
      <button type="submit" class="c-btn c-btn--primary" :disabled="pending">保存</button>
    </form>
  </AuthLayout>
</template>
