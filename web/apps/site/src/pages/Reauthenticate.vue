<script lang="ts">
import type { LoadCtx } from "../router"
import { safeNext } from "@sjtu-ow/shared/navigation"
export function load(ctx: LoadCtx) { return { title: "确认身份", next: safeNext(ctx.query.next, "/me/security/") } }
</script>
<script setup lang="ts">
import { inject, ref } from "vue"
import { useHead } from "@unhead/vue"
import { postApiAuthReauthenticate } from "@sjtu-ow/api"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
import AuthError from "@sjtu-ow/ui/AuthError.vue"
import CField from "@sjtu-ow/ui/CField.vue"
import { useApi } from "../api"
import { finishAccountAction, useAccountForm } from "../account-form"
const data = inject<{ next: string }>("page-data")
const api = useApi()
const password = ref("")
const { pending, message, fields, submit } = useAccountForm()
useHead({ title: "确认身份 · SJTU-OW" })
function reauthenticate() { return submit(async () => { await postApiAuthReauthenticate(api, { password: password.value }); finishAccountAction(safeNext(data?.next, "/me/security/")) }) }
</script>
<template>
  <AuthLayout><h1>确认身份</h1><p>为了保护账号，请再次输入密码。</p>
    <form method="post" action="/accounts/reauthenticate/" :aria-busy="pending || undefined" @submit.prevent="reauthenticate">
      <AuthError :message="message" /><CField label="密码" input-id="id_password" required :errors="fields.password"><input id="id_password" v-model="password" type="password" name="password" placeholder="密码" autocomplete="current-password" required aria-describedby="id_password_helptext"><template #help><a id="id_password_helptext" href="/accounts/password/reset/">忘记密码？</a></template></CField>
      <input type="hidden" name="next" :value="data?.next"><button type="submit" class="c-btn c-btn--primary" :disabled="pending">确认</button>
    </form>
  </AuthLayout>
</template>
