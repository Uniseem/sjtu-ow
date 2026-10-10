<script lang="ts">
import type { LoadCtx } from "../router"
import { safeNext } from "@sjtu-ow/shared/navigation"
export function load(ctx: LoadCtx) { return { title: "注册", next: safeNext(ctx.query.next, "/me/") } }
</script>
<script setup lang="ts">
import { computed, inject, ref } from "vue"
import { useHead } from "@unhead/vue"
import { postApiAuthRegister } from "@sjtu-ow/api"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
import AuthError from "@sjtu-ow/ui/AuthError.vue"
import AuthNewPasswords from "@sjtu-ow/ui/AuthNewPasswords.vue"
import CField from "@sjtu-ow/ui/CField.vue"
import { useApi } from "../api"
import { finishAccountAction, useAccountForm } from "../account-form"
const data = inject<{ next: string }>("page-data")
const next = computed(() => safeNext(data?.next, "/me/"))
const api = useApi()
const email = ref("")
const nickname = ref("")
const password = ref("")
const confirmation = ref("")
const sjtu = ref("")
const agreeTerms = ref(false)
const agreeCrossBorder = ref(false)
const { pending, message, fields, submit } = useAccountForm()
useHead({ title: "注册 · SJTU-OW" })
function signup() {
  return submit(async () => {
    const result = await postApiAuthRegister(api, { email: email.value.trim(), nickname: nickname.value.trim(), password: password.value, confirm_password: confirmation.value, is_sjtu: sjtu.value === "" ? null : sjtu.value === "true", agree_terms: agreeTerms.value, agree_cross_border: agreeCrossBorder.value }, { unauthorized: "throw" })
    finishAccountAction("/accounts/confirm-email/?" + new URLSearchParams({ email: result.email, next: next.value, welcome: "1" }))
  })
}
</script>
<template>
  <AuthLayout why>
    <h1>注册</h1><p>已经有账号？<a :href="'/accounts/login/' + (next !== '/me/' ? '?next=' + encodeURIComponent(next) : '')" class="c-link">登录</a></p>
    <form method="post" action="/accounts/signup/" :aria-busy="pending || undefined" @submit.prevent="signup">
      <AuthError :message="message" />
      <CField label="邮箱" input-id="id_email" required :errors="fields.email"><input id="id_email" v-model="email" type="email" name="email" autocomplete="email" placeholder="邮箱" maxlength="320" required></CField>
      <CField label="昵称" input-id="id_nickname" required :errors="fields.nickname"><input id="id_nickname" v-model="nickname" type="text" name="nickname" autocomplete="nickname" maxlength="16" minlength="2" required></CField>
      <AuthNewPasswords v-model:password="password" v-model:confirmation="confirmation" fresh :errors="fields" />
      <CField label="是否来自上海交通大学" kind="group" required :errors="fields.is_sjtu">
        <div id="id_is_sjtu"><div><label for="id_is_sjtu_0"><input id="id_is_sjtu_0" v-model="sjtu" type="radio" name="is_sjtu" value="true" required> 是</label></div><div><label for="id_is_sjtu_1"><input id="id_is_sjtu_1" v-model="sjtu" type="radio" name="is_sjtu" value="false" required> 否</label></div></div>
      </CField>
      <CField label="我已阅读并同意用户协议和隐私政策" kind="checkbox" input-id="id_agreed_terms" required :errors="fields.agree_terms"><input id="id_agreed_terms" v-model="agreeTerms" type="checkbox" name="agreed_terms" required></CField>
      <CField label="我同意将个人信息存储在境外服务器" kind="checkbox" input-id="id_agreed_cross_border" required :errors="fields.agree_cross_border"><input id="id_agreed_cross_border" v-model="agreeCrossBorder" type="checkbox" name="agreed_cross_border" required></CField>
      <input v-if="next !== '/me/'" type="hidden" name="next" :value="next">
      <p class="text-sm text-fg-2">请先阅读<a href="/terms/" class="c-link" target="_blank" rel="noopener">用户协议</a>和<a href="/privacy/" class="c-link" target="_blank" rel="noopener">隐私政策</a>（在新标签页打开），两项同意要分别勾选。</p>
      <div><button type="submit" class="c-btn c-btn--primary c-btn--block" :disabled="pending">注册</button></div>
    </form>
  </AuthLayout>
</template>
