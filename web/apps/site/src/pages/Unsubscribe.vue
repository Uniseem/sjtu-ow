<script lang="ts">
import type { LoadCtx } from "../router"
import { ApiError, getApiAnnouncementsUnsubscribeToken } from "@sjtu-ow/api"

export async function load(ctx: LoadCtx) {
  try {
    const subscription = await getApiAnnouncementsUnsubscribeToken(ctx.api, ctx.params.token, { unauthorized: "throw" })
    return { title: "退订活动通知", subscription, token: ctx.params.token, invalid: false }
  } catch (error) {
    // Invalid signed links have a real explanation page in the old site.
    if (error instanceof ApiError && (error.status === 400 || error.status === 404)) {
      return { title: "退订活动通知", subscription: null, token: ctx.params.token, invalid: true }
    }
    throw error
  }
}
</script>

<script setup lang="ts">
import { inject, ref } from "vue"
import { useHead } from "@unhead/vue"
import { postApiAnnouncementsUnsubscribeToken } from "@sjtu-ow/api"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import { requirePageData } from "../personal"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"

const data = requirePageData(inject<{
  subscription: { nickname?: string; accepts: boolean } | null
  token: string
  invalid: boolean
}>("page-data"))
const api = useApi()
const done = ref(data.subscription?.accepts === false)
const nickname = ref(data.subscription?.nickname ?? "")
const mutation = useMutation(
  (token: string, extras) => postApiAnnouncementsUnsubscribeToken(api, token, extras),
  (result) => {
    done.value = !result.accepts
    nickname.value = result.nickname ?? nickname.value
  },
)

useHead({ title: "退订活动通知 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })
</script>

<template>
  <AuthLayout>
    <h1>退订活动通知</h1>
    <template v-if="data.invalid">
      <p>这个退订链接无效，可能复制时缺了一段。登录后在「个人中心 → 账号安全」里也能关掉活动通知。</p>
      <div><a href="/me/security/" class="c-btn c-btn--secondary">去账号安全</a></div>
    </template>
    <template v-else-if="done">
      <p>{{ nickname }}，已经退订：之后发布新赛事、新内战时不会再给你发信。</p>
      <p>报名、战队、审核结果这些和你本人有关的邮件照常会发。想重新收到活动通知，登录后在「个人中心 → 账号安全」里打开。</p>
      <div><a href="/" class="c-btn c-btn--secondary">回到首页</a></div>
    </template>
    <template v-else>
      <p>{{ nickname }}，确定不再接收活动通知吗？之后发布新赛事、新内战时不会再给你发信；和你本人有关的邮件照常会发。</p>
      <form method="post" :aria-busy="mutation.pending.value || undefined" @submit.prevent="mutation.submit(data.token)">
        <CMutationError
          :message="mutation.message.value"
          :uncertain="mutation.uncertain.value"
          :pending="mutation.pending.value"
          @retry="mutation.retry"
        />
        <div>
          <button type="submit" class="c-btn c-btn--primary c-btn--block" :disabled="!mutation.canStart.value">退订</button>
        </div>
      </form>
    </template>
  </AuthLayout>
</template>
