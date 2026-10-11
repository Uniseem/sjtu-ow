<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiMeAnnouncements } from "@sjtu-ow/api"
import { httpError } from "../router"

export async function load(ctx: LoadCtx) {
  const viewer = await ctx.viewer()
  if (!viewer.user) throw httpError(401)
  return { title: "账号安全", user: viewer.user, announcements: await getApiMeAnnouncements(ctx.api) }
}
</script>

<script setup lang="ts">
import { inject, ref } from "vue"
import { useHead } from "@unhead/vue"
import {
  getApiMeExport,
  postApiAuthLogout,
  postApiMeAnnouncements,
} from "@sjtu-ow/api"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import PersonalSessionLayout from "../components/PersonalSessionLayout.vue"
import { requirePageData } from "../personal"
import type { ViewerUser } from "../viewer"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import { useAccountForm, finishAccountAction } from "../account-form"
import { downloadJSON } from "../upload"

const data = requirePageData(inject<{ user: ViewerUser; announcements: { accepts: boolean } }>("page-data"))
const api = useApi()
const accepts = ref(data.announcements.accepts)
const notice = ref("")
const notifications = useMutation(
  (body: { accepts: boolean }, extras) => postApiMeAnnouncements(api, body, extras),
  (result) => {
    accepts.value = result.accepts
    notice.value = result.accepts ? "已打开活动通知。" : "已关闭活动通知。"
  },
)
const logout = useMutation(
  (_body: Record<string, never>, extras) => postApiAuthLogout(api, extras),
  () => finishAccountAction("/"),
)
const exporting = useAccountForm()

function toggle(): void {
  notice.value = ""
  void notifications.submit({ accepts: !accepts.value })
}

function exportAccount(): void {
  void exporting.submit(async () => {
    const result = await getApiMeExport(api, { unauthorized: "throw" })
    downloadJSON(result, "sjtu-ow-personal-information.json")
  })
}

useHead({ title: "账号安全 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })
</script>

<template>
  <PersonalSessionLayout title="账号安全" current="/me/security/" :user="data.user">
    <section aria-labelledby="me-login">
      <SectionHead title="登录" heading-id="me-login" />
      <ul class="c-rows max-w-3xl">
        <li class="c-row c-row--plain">
          <div class="c-row__main">
            <h3 class="c-row__title">密码</h3>
            <p class="c-row__text">登录时用的密码。</p>
          </div>
          <a href="/accounts/password/change/" class="c-btn c-btn--secondary">修改密码</a>
        </li>
        <li class="c-row c-row--plain">
          <div class="c-row__main">
            <h3 class="c-row__title">邮箱</h3>
            <p class="c-row__text">用于登录和接收验证码，只有你自己和超级管理员能看到。</p>
          </div>
          <a href="/accounts/email/" class="c-btn c-btn--secondary">修改邮箱</a>
        </li>
        <li class="c-row c-row--plain">
          <div class="c-row__main">
            <h3 class="c-row__title">退出登录</h3>
            <p class="c-row__text">在这台设备上退出。</p>
          </div>
          <form method="post" action="/accounts/logout/" @submit.prevent="logout.submit({})">
            <button type="submit" class="c-btn c-btn--secondary" :disabled="!logout.canStart.value">退出登录</button>
          </form>
        </li>
      </ul>
      <CMutationError
        :message="logout.message.value"
        :uncertain="logout.uncertain.value"
        :pending="logout.pending.value"
        @retry="logout.retry"
      />
    </section>
    <section aria-labelledby="me-mail">
      <SectionHead title="邮件通知" heading-id="me-mail" />
      <ul class="c-rows max-w-3xl">
        <li class="c-row c-row--plain">
          <div class="c-row__main">
            <h3 class="c-row__title">活动通知：{{ accepts ? '开着' : '关着' }}</h3>
            <p class="c-row__text">发布新赛事、新内战时，管理员可以给全体成员发信。报名、战队、审核结果这些和你本人有关的邮件不受影响。</p>
          </div>
          <form method="post" action="/me/notifications/" @submit.prevent="toggle">
            <input type="hidden" name="accepts_announcements" :value="accepts ? '0' : '1'">
            <button type="submit" class="c-btn c-btn--secondary" :disabled="!notifications.canStart.value">
              {{ accepts ? '关闭活动通知' : '打开活动通知' }}
            </button>
          </form>
        </li>
      </ul>
      <CMutationError
        :message="notifications.message.value"
        :uncertain="notifications.uncertain.value"
        :pending="notifications.pending.value"
        @retry="notifications.retry"
      />
      <p v-if="notice" class="text-sm text-fg-2" role="status">{{ notice }}</p>
    </section>
    <section aria-labelledby="me-data">
      <SectionHead title="个人信息" heading-id="me-data" />
      <ul class="c-rows max-w-3xl">
        <li class="c-row c-row--plain">
          <div class="c-row__main">
            <h3 class="c-row__title">导出</h3>
            <p class="c-row__text">下载本站保存的你的全部个人信息（JSON 文件）。</p>
          </div>
          <button type="button" class="c-btn c-btn--secondary" :disabled="exporting.pending.value" @click="exportAccount">
            <CIcon name="download" />导出我的个人信息
          </button>
        </li>
        <li class="c-row c-row--plain">
          <div class="c-row__main">
            <h3 class="c-row__title">注销账号</h3>
            <p class="c-row__text">删除邮箱、游戏 ID 和联系方式，昵称改为「已注销用户」。不能恢复。</p>
          </div>
          <a href="/me/delete/" class="c-btn c-btn--danger">注销账号</a>
        </li>
      </ul>
      <CMutationError :message="exporting.message.value" />
    </section>
  </PersonalSessionLayout>
</template>
