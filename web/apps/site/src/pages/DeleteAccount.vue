<script lang="ts">
import type { LoadCtx } from "../router"
import { loadPersonal } from "../personal"

export function load(ctx: LoadCtx) {
  return loadPersonal(ctx, "注销账号")
}
</script>

<script setup lang="ts">
import { computed, inject, ref } from "vue"
import { useHead } from "@unhead/vue"
import { getApiMeExport, postApiAuthDeleteAccount } from "@sjtu-ow/api"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CField from "@sjtu-ow/ui/CField.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import PersonalLayout from "../components/PersonalLayout.vue"
import { requirePageData, usePersonalUser } from "../personal"
import type { PersonalPageData } from "../personal"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import { useAccountForm, finishAccountAction } from "../account-form"
import { downloadJSON } from "../upload"

const data = requirePageData(inject<PersonalPageData>("page-data"))
const user = usePersonalUser(data.profile)
const api = useApi()
const password = ref("")
const blockers = computed(() => data.profile.deletion_blockers)
const available = computed(() => Array.isArray(blockers.value) && blockers.value.length === 0)
const mutation = useMutation(
  (body: { password: string }, extras) => postApiAuthDeleteAccount(api, body, extras),
  () => {
    password.value = ""
    finishAccountAction("/")
  },
)
const exporting = useAccountForm()

function remove(): void {
  if (!available.value) return
  void mutation.submit({ password: password.value })
}

function exportAccount(): void {
  void exporting.submit(async () => {
    const result = await getApiMeExport(api, { unauthorized: "throw" })
    downloadJSON(result, "sjtu-ow-personal-information.json")
  })
}

useHead({ title: "注销账号 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })
</script>

<template>
  <PersonalLayout title="注销账号" current="/me/security/" :profile="data.profile" :user="user">
    <div class="flex max-w-2xl flex-col gap-8">
      <div class="c-notice c-notice--error">
        <CIcon name="alert" />
        <div class="c-notice__body">
          <p class="font-semibold">注销后不能恢复。</p>
          <ul class="mt-2 list-[square] pl-5">
            <li>邮箱、游戏 ID、联系方式会被删除，昵称改为「已注销用户」</li>
            <li>你会退出所有战队，内战报名会被取消</li>
            <li>已经提交的赛事报名名单会保留提交时的记录；你署名的文章会保留，署名显示「已注销用户」</li>
            <li>之后可以用同一个邮箱重新注册一个新账号</li>
          </ul>
        </div>
      </div>
      <p class="text-fg-2">
        注销前可以先<button type="button" class="c-link" :disabled="exporting.pending.value" @click="exportAccount">导出你的个人信息</button>。
      </p>
      <CMutationError :message="exporting.message.value" />
      <div v-if="blockers?.length" class="c-notice c-notice--warn" role="alert" data-deletion-blocked>
        <CIcon name="alert" />
        <ul class="c-notice__body list-[square] pl-5">
          <li v-for="reason in blockers" :key="reason">{{ reason }}</li>
        </ul>
      </div>
      <p v-else-if="!available" class="text-fg-2" role="status">暂时无法确认账号状态，请稍后再试。</p>
      <form
        v-else
        method="post"
        action="/me/delete/"
        class="c-form max-w-md"
        :aria-busy="mutation.pending.value || undefined"
        @submit.prevent="remove"
      >
        <CMutationError
          :message="Object.keys(mutation.fields.value).length ? '' : mutation.message.value"
          :uncertain="mutation.uncertain.value"
          :pending="mutation.pending.value"
          @retry="mutation.retry"
        />
        <CField label="当前密码" input-id="id_password" required :errors="mutation.fields.value.password">
          <input
            id="id_password"
            v-model="password"
            type="password"
            name="password"
            autocomplete="current-password"
            required
            :disabled="mutation.pending.value || mutation.uncertain.value"
          >
        </CField>
        <div class="c-formbar">
          <button type="submit" class="c-btn c-btn--danger" :disabled="!mutation.canStart.value">确认注销</button>
        </div>
      </form>
    </div>
  </PersonalLayout>
</template>
