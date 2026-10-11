<script lang="ts">
import type { LoadCtx } from "../router"
import { httpError } from "../router"
import { getApiMeRegistrations } from "@sjtu-ow/api"
import { personalRegistrations } from "../personal-list-schema"

export async function load(ctx: LoadCtx) {
  const viewer = await ctx.viewer()
  if (!viewer.user) throw httpError(401)
  return { title: "我的报名", user: viewer.user, registrations: personalRegistrations(await getApiMeRegistrations(ctx.api)) }
}
</script>

<script setup lang="ts">
import { inject, reactive, ref, watch } from "vue"
import { useHead } from "@unhead/vue"
import { deleteApiTournamentsIdSignup } from "@sjtu-ow/api"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import { owDate } from "@sjtu-ow/shared/time"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import CRegStatus from "@sjtu-ow/ui/CRegStatus.vue"
import CRoleIcon from "@sjtu-ow/ui/CRoleIcon.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"
import PersonalSessionLayout from "../components/PersonalSessionLayout.vue"
import PersonalCalendar from "../components/PersonalCalendar.vue"
import { requirePageData } from "../personal"
import type { ViewerUser } from "../viewer"
import { registrationLabel, signupStatus } from "../registration-display"
import type { PersonalRegistrations } from "../registration-display"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"

const data = requirePageData(inject<{ user: ViewerUser; registrations: PersonalRegistrations }>("page-data"))
const registrations = reactive({ ...data.registrations })
const api = useApi()
const confirm = useConfirm()
const cancellingId = ref<number | null>(null)
const notice = ref("")
const cancel = useMutation(
  (id: number, extras) => deleteApiTournamentsIdSignup(api, id, extras),
  () => {
    registrations.individual_signups = registrations.individual_signups?.filter((signup) => signup.tournament_id !== cancellingId.value)
    notice.value = "个人报名已取消。"
  },
)

function cancelSignup(id: number): void {
  if (!cancel.canStart.value || !confirm("取消这项赛事的个人报名？")) return
  cancellingId.value = id
  notice.value = ""
  void cancel.submit(id)
}

watch(() => data.registrations, (next) => { Object.assign(registrations, next) })
useHead({ title: "我的报名 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })
</script>

<template>
  <PersonalSessionLayout title="我的报名" current="/me/registrations/" :user="data.user">
    <p v-if="notice" class="text-sm text-fg-2" role="status">{{ notice }}</p>
    <section aria-labelledby="me-regs">
      <SectionHead title="赛事报名" heading-id="me-regs" />
      <table v-if="registrations.registrations.length" class="c-table c-table--stack">
        <thead>
          <tr><th scope="col">赛事</th><th scope="col">比赛时间</th><th scope="col">队伍</th><th scope="col">状态</th><th scope="col" class="is-num">提交</th></tr>
        </thead>
        <tbody>
          <tr v-for="registration in registrations.registrations" :key="registration.registration_id">
            <td data-label="赛事">
              <a :href="'/registrations/' + registration.registration_id + '/'" class="font-semibold hover:text-primary-text">{{ registration.title }}</a>
            </td>
            <td data-label="比赛时间" class="font-numeric" data-starts>{{ registration.starts_label }}</td>
            <td data-label="队伍">
              {{ registration.team_name }}
              <span v-if="registration.team_id === null" class="c-tag ml-1">临时队伍</span>
            </td>
            <td data-label="状态"><CRegStatus :status="registration.status" :label="registrationLabel(registration.status, registration.status_label)" /></td>
            <td data-label="提交" class="is-num font-numeric">{{ owDate(new Date(registration.submitted_at)) }}</td>
          </tr>
        </tbody>
      </table>
      <CEmpty v-else title="还没有参加赛事报名" message="战队报名由队长提交，名单里有你就会出现在这里。" action-url="/tournaments/" action-label="去看看赛事" />
    </section>
    <section v-if="registrations.individual_signups !== undefined" aria-labelledby="me-individual">
      <SectionHead title="个人报名" heading-id="me-individual" />
      <table v-if="registrations.individual_signups.length" class="c-table c-table--stack">
        <thead>
          <tr><th scope="col">赛事</th><th scope="col">比赛时间</th><th scope="col">游戏 ID</th><th scope="col">位置</th><th scope="col">状态</th><th scope="col" class="is-num">操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="signup in registrations.individual_signups" :key="signup.id">
            <td data-label="赛事"><a :href="'/tournaments/' + signup.tournament_id + '/'" class="font-semibold hover:text-primary-text">{{ signup.title }}</a></td>
            <td data-label="比赛时间" class="font-numeric" data-starts>{{ signup.starts_label }}</td>
            <td data-label="游戏 ID" class="font-code">{{ signup.battletag ?? '游戏 ID 已删除' }}</td>
            <td data-label="位置"><CRoleIcon :tank="signup.role_tank" :damage="signup.role_damage" :support="signup.role_support" /></td>
            <td data-label="状态"><CStatus :kind="signupStatus(signup).kind" :label="signupStatus(signup).label" /></td>
            <td data-label="操作" class="is-num">
              <a v-if="signup.registration_id !== null" :href="'/registrations/' + signup.registration_id + '/'" class="c-btn c-btn--secondary c-btn--sm">查看报名</a>
              <form v-else-if="signup.registration_open" method="post" :action="'/tournaments/' + signup.tournament_id + '/signup/cancel/'" class="inline-block" @submit.prevent="cancelSignup(signup.tournament_id)">
                <button type="submit" class="c-btn c-btn--danger c-btn--sm" :disabled="!cancel.canStart.value">取消个人报名</button>
              </form>
            </td>
          </tr>
        </tbody>
      </table>
      <CEmpty v-else title="没有个人报名" message="标着「个人报名」的赛事，在赛事页就能报名。" />
      <CMutationError :message="cancel.message.value" :uncertain="cancel.uncertain.value" :pending="cancel.pending.value" @retry="cancel.retry" />
    </section>
    <section aria-labelledby="me-scrim-link">
      <SectionHead title="内战报名" heading-id="me-scrim-link" />
      <p class="text-fg-2">内战报名在<a href="/me/scrims/" class="c-link">我的内战</a>里查看。</p>
    </section>
    <PersonalCalendar v-if="registrations.calendar" :calendar="registrations.calendar" />
  </PersonalSessionLayout>
</template>
