<script lang="ts">
import type { LoadCtx } from "../router"
import { safeNext } from "@sjtu-ow/shared/navigation"
export function load(ctx: LoadCtx) { return { title: "登录", next: safeNext(ctx.query.next) } }
</script>
<script setup lang="ts">
import { computed, inject, ref } from "vue"
import { useHead } from "@unhead/vue"
import { postApiAuthLogin } from "@sjtu-ow/api"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
import AuthError from "@sjtu-ow/ui/AuthError.vue"
import CField from "@sjtu-ow/ui/CField.vue"
import { useApi } from "../api"
import { finishAccountAction, useAccountForm } from "../account-form"
const data = inject<{ next: string }>("page-data")
const next = computed(() => safeNext(data?.next))
const api = useApi()
const email = ref("")
const password = ref("")
const { pending, message, fields, submit } = useAccountForm()
useHead({ title: "登录 · SJTU-OW" })
function login() {
  return submit(async () => {
    const result = await postApiAuthLogin(api, { email: email.value.trim(), password: password.value }, { unauthorized: "throw" })
    if (result.result === "verify_required") {
      finishAccountAction("/accounts/confirm-email/?" + new URLSearchParams({ email: email.value.trim(), next: next.value }))
    } else { finishAccountAction(next.value) }
  })
}
</script>
<template>
  <AuthLayout why>
    <h1>登录</h1><p>还没有账号？<a :href="'/accounts/signup/' + (next !== '/' ? '?next=' + encodeURIComponent(next) : '')" class="c-link">注册</a></p>
    <form method="post" action="/accounts/login/" :aria-busy="pending || undefined" @submit.prevent="login">
      <AuthError :message="message" />
      <CField label="邮箱" input-id="id_login" required :errors="fields.email"><input id="id_login" v-model="email" type="email" name="login" autocomplete="email" placeholder="邮箱" maxlength="320" required></CField>
      <CField label="密码" input-id="id_password" required :errors="fields.password">
        <input id="id_password" v-model="password" type="password" name="password" placeholder="密码" autocomplete="current-password" required>
      </CField>
      <input v-if="next !== '/'" type="hidden" name="next" :value="next">
      <div><button type="submit" class="c-btn c-btn--primary c-btn--block" :disabled="pending">登录</button></div>
    </form>
    <p class="c-auth__foot"><a href="/accounts/password/reset/" class="c-link">忘记密码？</a></p>
  </AuthLayout>
</template>
