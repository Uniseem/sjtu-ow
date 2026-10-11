<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiMeTeams } from "@sjtu-ow/api"
import { httpError } from "../router"
import { personalMemberships } from "../personal-list-schema"

export async function load(ctx: LoadCtx) {
  const viewer = await ctx.viewer()
  if (!viewer.user) throw httpError(401)
  return { title: "我的战队", user: viewer.user, memberships: personalMemberships(await getApiMeTeams(ctx.api)) }
}
</script>

<script setup lang="ts">
import { inject, reactive, ref, watch } from "vue"
import { useHead } from "@unhead/vue"
import {
  postApiTeamsIdLeave,
  postApiTeamApplicationsIdCancel,
} from "@sjtu-ow/api"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import { owDate } from "@sjtu-ow/shared/time"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"
import PersonalSessionLayout from "../components/PersonalSessionLayout.vue"
import TeamAlumni from "../components/TeamAlumni.vue"
import { applicationStatus } from "../team-display"
import type { PersonalMemberships } from "../team-display"
import { requirePageData } from "../personal"
import type { ViewerUser } from "../viewer"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"

const data = requirePageData(inject<{ user: ViewerUser; memberships: PersonalMemberships }>("page-data"))
const memberships = reactive({ ...data.memberships, teams: [...data.memberships.teams], applications: [...data.memberships.applications] })
const api = useApi()
const confirm = useConfirm()
const notice = ref("")
const leavingId = ref<number | null>(null)
const cancelId = ref<number | null>(null)
const leave = useMutation(
  (id: number, extras) => postApiTeamsIdLeave(api, id, extras),
  () => {
    memberships.teams = memberships.teams.filter((team) => team.team_id !== leavingId.value)
    notice.value = "已退出战队。"
  },
)
const cancel = useMutation(
  (id: number, extras) => postApiTeamApplicationsIdCancel(api, id, extras),
  () => {
    const application = memberships.applications.find((item) => item.id === cancelId.value)
    if (application) application.status = "cancelled"
    notice.value = "入队申请已撤回。"
  },
)

function leaveTeam(id: number): void {
  if (!leave.canStart.value || !confirm("确定退出这支战队？")) return
  leavingId.value = id
  notice.value = ""
  void leave.submit(id)
}

function cancelApplication(id: number): void {
  if (!cancel.canStart.value || !confirm("撤回这份入队申请？")) return
  cancelId.value = id
  notice.value = ""
  void cancel.submit(id)
}

watch(() => data.memberships, (next) => {
  Object.assign(memberships, next, { teams: [...next.teams], applications: [...next.applications] })
})

useHead({ title: "我的战队 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })
</script>

<template>
  <PersonalSessionLayout title="我的战队" current="/me/teams/" :user="data.user">
    <template #actions>
      <a href="/teams/new/" class="c-btn c-btn--secondary"><CIcon name="plus" />创建战队</a>
    </template>
    <p v-if="notice" class="text-sm text-fg-2" role="status">{{ notice }}</p>
    <section aria-labelledby="me-teams">
      <SectionHead title="我所在的战队" heading-id="me-teams" />
      <table v-if="memberships.teams.length" class="c-table c-table--stack">
        <thead>
          <tr><th scope="col">战队</th><th scope="col">身份</th><th scope="col">队内联系方式</th><th scope="col" class="is-num">操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="team in memberships.teams" :key="team.team_id">
            <td data-label="战队"><a :href="'/teams/' + team.team_id + '/'" class="font-semibold hover:text-primary-text">{{ team.name }}</a></td>
            <td data-label="身份"><span v-if="team.role === 'captain'" class="c-tag c-tag--strong">队长</span><template v-else>队员</template></td>
            <td data-label="队内联系方式" data-member-contact>
              <template v-if="team.member_contact !== undefined">
                <span v-if="team.member_contact" class="font-code">{{ team.member_contact }}</span>
                <a v-else-if="team.role === 'captain'" :href="'/teams/' + team.team_id + '/manage/#manage-profile'" class="c-link text-sm">还没填，去填</a>
                <span v-else class="text-sm text-fg-3">队长还没填</span>
              </template>
            </td>
            <td data-label="操作" class="is-num">
              <a v-if="team.role === 'captain'" :href="'/teams/' + team.team_id + '/manage/'" class="c-btn c-btn--secondary c-btn--sm"><CIcon name="settings" />管理</a>
              <form v-else method="post" :action="'/teams/' + team.team_id + '/leave/'" class="inline-block" @submit.prevent="leaveTeam(team.team_id)">
                <button type="submit" class="c-btn c-btn--danger c-btn--sm" :disabled="!leave.canStart.value">退出</button>
              </form>
            </td>
          </tr>
        </tbody>
      </table>
      <CEmpty v-else title="还没有加入战队" message="去战队页看看谁在招人，或者自己创建一支。" action-url="/teams/" action-label="去看看战队" />
      <CMutationError :message="leave.message.value" :uncertain="leave.uncertain.value" :pending="leave.pending.value" @retry="leave.retry" />
    </section>
    <TeamAlumni v-if="memberships.alumni" :records="memberships.alumni" />
    <section aria-labelledby="me-applications">
      <SectionHead title="我的入队申请" heading-id="me-applications" />
      <table v-if="memberships.applications.length" class="c-table c-table--stack">
        <thead>
          <tr><th scope="col">战队</th><th scope="col">状态</th><th scope="col">提交</th><th scope="col" class="is-num">操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="application in memberships.applications" :key="application.id">
            <td data-label="战队"><a :href="'/teams/' + application.team_id + '/'" class="font-semibold hover:text-primary-text">{{ application.team_name }}</a></td>
            <td data-label="状态">
              <CStatus :kind="applicationStatus(application.status).kind" :label="applicationStatus(application.status).label" />
              <span v-if="application.decision_note" class="mt-1 block text-sm text-fg-2">{{ application.decision_note }}</span>
            </td>
            <td data-label="提交" class="font-numeric">{{ owDate(new Date(application.created_at)) }}</td>
            <td data-label="操作" class="is-num">
              <form v-if="application.status === 'pending'" method="post" :action="'/teams/applications/' + application.id + '/cancel/'" class="inline-block" @submit.prevent="cancelApplication(application.id)">
                <button type="submit" class="c-btn c-btn--secondary c-btn--sm" :disabled="!cancel.canStart.value">撤回</button>
              </form>
            </td>
          </tr>
        </tbody>
      </table>
      <CEmpty v-else title="还没有提交过入队申请" />
      <CMutationError :message="cancel.message.value" :uncertain="cancel.uncertain.value" :pending="cancel.pending.value" @retry="cancel.retry" />
    </section>
  </PersonalSessionLayout>
</template>
