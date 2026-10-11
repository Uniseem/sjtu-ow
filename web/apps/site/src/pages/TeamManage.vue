<script lang="ts">
import type { LoadCtx } from "../router"
import { requireTeam as loadedTeam } from "../team-domain"
import { getApiTeamsIdManage as loadManage } from "@sjtu-ow/api"
export async function load(ctx: LoadCtx) {
  const page = await loadManage(ctx.api, ctx.params.id)
  return { title: "管理 " + loadedTeam(page.team).name, page: {...page,team:loadedTeam(page.team)} }
}
</script>
<script setup lang="ts">
import { computed, inject, reactive, ref } from "vue"
import { useHead } from "@unhead/vue"
import { getApiTeamsIdManage, patchApiTeamsId, postApiTeamsIdDisband, postApiTeamAlumniIdRemove } from "@sjtu-ow/api"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import CAutosave from "@sjtu-ow/ui/CAutosave.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import CTeamLogo from "@sjtu-ow/ui/CTeamLogo.vue"
import CField from "@sjtu-ow/ui/CField.vue"
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"
import TeamFields from "../components/TeamFields.vue"
import TeamLogoUpload from "../components/TeamLogoUpload.vue"
import TeamApplication from "../components/TeamApplication.vue"
import TeamManageMember from "../components/TeamManageMember.vue"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import { owDate } from "@sjtu-ow/shared/time"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import { useAutosave } from "../use-autosave"
import { requirePageData } from "../personal"
import { teamValues, readTeamCurrent } from "../team-editor"
import { finishAccountAction } from "../account-form"
import type { TeamManage } from "../team-domain"
const data = requirePageData(inject<{ page: TeamManage }>("page-data"))
const page = reactive(structuredClone(data.page))
const api = useApi()
const confirm = useConfirm()
const message = ref("")
const uploading = ref(false)
const save = useAutosave({ initial: teamValues(page.team), version: page.team.version, readCurrent: readTeamCurrent,
  together: [["is_recruiting", "recruiting_roles"]], transport: async (body, key, signal) => { const receipt=await patchApiTeamsId(api,page.team.id,body,{key,signal,unauthorized:"throw"});return {...receipt,values:receipt.values??undefined} } })
const currentTeam = computed(() => ({ ...page.team, name: save.values.value.name, logo_image_id: save.values.value.logo_image_id }))
const disband = useMutation((_body: Record<string, never>, extras) => postApiTeamsIdDisband(api, page.team.id, extras), () => finishAccountAction("/teams/" + page.team.id + "/"))
const alumni = useMutation((body: { id: number }, extras) => postApiTeamAlumniIdRemove(api, body.id, extras), () => refresh())
useHead(computed(() => ({ title: "管理 " + currentTeam.value.name + " · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })))
async function refresh(): Promise<void> {
  try {
    const next = await getApiTeamsIdManage(api, page.team.id, { unauthorized: "throw" })
    if(!next.team)throw new Error("战队已不存在，请返回我的战队。")
    Object.assign(page, next)
    message.value = ""
  } catch (failure) {
    message.value = failure instanceof Error ? failure.message : "操作已完成，但列表未能刷新，请重新打开页面。"
  }
}
async function logoChanged(): Promise<void> {
  await refresh()
  if (!save.controller.reset(teamValues(page.team), page.team.version)) message.value = "队标已上传，资料中仍有未保存内容，请保存后重新打开页面。"
}
function removeAlumnus(id: number): void {
  if (confirm("从退役名单里去掉这个人？")) void alumni.submit({ id })
}
async function dissolve(): Promise<void> {
  if (page.disband_blockers.length || !await save.flush()) return
  if (confirm("确定解散战队？解散后不能恢复。")) void disband.submit({})
}
function reason(value: string): string { return ({ left: "退出", removed: "移除", disbanded: "解散" } as Record<string,string>)[value] || value }
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead">
      <div class="l-container l-container--narrow">
        <nav class="c-crumbs" aria-label="位置"><a href="/">首页</a><span class="c-crumbs__sep">/</span><a href="/teams/">战队</a><span class="c-crumbs__sep">/</span><a :href="'/teams/' + page.team.id + '/'">{{ currentTeam.name }}</a><span class="c-crumbs__sep">/</span><span>管理</span></nav>
        <div class="c-pagehead__row">
          <div><h1>管理「{{ currentTeam.name }}」</h1><p class="c-pagehead__meta"><span>成员 <span class="font-numeric">{{ page.members.length }} / {{ page.max_members }}</span></span><span>待审批 <span class="font-numeric">{{ page.pending.length }}</span></span></p></div>
          <div class="c-pagehead__actions"><a :href="'/teams/' + page.team.id + '/'" class="c-btn c-btn--secondary">查看主页</a></div>
        </div>
      </div>
    </header>
    <div class="l-container l-container--narrow pt-8 pb-16 lg:pb-24">
      <p v-if="message" class="c-notice c-notice--warning" role="status">{{ message }}</p>
      <div class="flex max-w-4xl flex-col gap-14">
        <section aria-labelledby="manage-apps">
          <SectionHead title="待审批的申请" heading-id="manage-apps" />
          <ul v-if="page.pending.length" class="flex flex-col gap-4"><TeamApplication v-for="application in page.pending" :key="application.id" :application="application" @changed="refresh" /></ul>
          <CEmpty v-else title="暂时没有待审批的申请" message="有人申请加入时会出现在这里。" />
        </section>
        <section aria-labelledby="manage-roster">
          <SectionHead title="成员" heading-id="manage-roster" />
          <table class="c-table c-table--stack">
            <thead><tr><th scope="col">昵称</th><th scope="col">位置与段位</th><th scope="col">游戏 ID</th><th scope="col" class="is-num">操作</th></tr></thead>
            <tbody><TeamManageMember v-for="member in page.members" :key="member.user_id" :team-id="page.team.id" :member="member" @changed="refresh" @transferred="finishAccountAction('/teams/' + page.team.id + '/')" /></tbody>
          </table>
        </section>
        <section v-if="page.alumni.length" aria-labelledby="manage-alumni" data-manage-alumni>
          <SectionHead title="退役成员" heading-id="manage-alumni" />
          <CMutationError :message="alumni.message.value" :uncertain="alumni.uncertain.value" :pending="alumni.pending.value" @retry="alumni.retry" />
          <table class="c-table c-table--stack">
            <thead><tr><th scope="col">昵称</th><th scope="col" class="is-num">入队</th><th scope="col" class="is-num">离队</th><th scope="col">方式</th><th scope="col" class="is-num">操作</th></tr></thead>
            <tbody>
              <tr v-for="record in page.alumni" :key="record.id">
                <td data-label="昵称"><span class="font-semibold">{{ record.nickname }}</span></td>
                <td data-label="入队" class="is-num font-numeric">{{ owDate(new Date(record.joined_at)) }}</td>
                <td data-label="离队" class="is-num font-numeric">{{ owDate(new Date(record.left_at)) }}</td>
                <td data-label="方式">{{ reason(record.reason) }}</td>
                <td data-label="操作" class="is-num"><form v-if="record.can_remove" method="post" @submit.prevent="removeAlumnus(record.id)"><button type="submit" class="c-btn c-btn--secondary c-btn--sm" :disabled="!alumni.canStart.value">从名单去掉</button></form></td>
              </tr>
            </tbody>
          </table>
        </section>
        <section aria-labelledby="manage-profile">
          <SectionHead title="战队资料" heading-id="manage-profile" />
          <form method="post" enctype="multipart/form-data" class="c-form max-w-xl" data-autosave :aria-busy="save.pending.value || undefined" @submit.prevent="save.save">
            <CAutosave
              class="contents"
              :state="save.snapshot.value.state"
              :message="save.snapshot.value.message || (save.snapshot.value.state === 'idle' && !save.dirty.value ? '改了就自动保存' : '')"
              :dirty="save.dirty.value"
              :pending="save.pending.value"
              :login-required="save.snapshot.value.loginRequired"
              :login-href="'/accounts/login/?next=' + encodeURIComponent('/teams/' + page.team.id + '/manage/')"
              @retry="save.save"
            />
            <input type="hidden" name="form" value="profile">
            <CTeamLogo :team="currentTeam" />
            <TeamFields :values="save.values.value" :fields="save.fields.value" :disabled="uploading" @text="(name, value) => save.set(name, value, 'text')" @choice="changes => save.setMany(changes, 'choice')" @blur="save.flush" />
            <TeamLogoUpload :team-id="page.team.id" :image-id="currentTeam.logo_image_id" :before-upload="save.flush" @changed="logoChanged" @busy="value => uploading = value" />
            <CField label="删除队标" kind="checkbox" input-id="id_remove_logo" :errors="save.fields.value.remove_logo">
              <input id="id_remove_logo" type="checkbox" name="remove_logo" :checked="save.values.value.remove_logo" :disabled="uploading" @change="save.set('remove_logo', ($event.target as HTMLInputElement).checked, 'choice')">
            </CField>
            <div class="c-formbar" hidden><button type="submit" class="c-btn c-btn--primary" data-autosave-button hidden :disabled="uploading || save.pending.value">保存</button></div>
          </form>
        </section>
        <section aria-labelledby="manage-disband">
          <SectionHead title="解散战队" heading-id="manage-disband" />
          <div class="c-notice c-notice--error max-w-2xl">
            <CIcon name="alert" /><div class="c-notice__body">
              <p>解散后成员会被清空、待审批的申请会取消，队名可以被其他战队使用。</p>
              <template v-if="page.disband_blockers.length"><ul class="mt-3 list-disc pl-5"><li v-for="(blocker, index) in page.disband_blockers" :key="index">{{ blocker }}</li></ul><button type="button" class="c-btn c-btn--danger mt-4" disabled>暂时不能解散</button></template>
              <form v-else method="post" class="mt-4" @submit.prevent="dissolve"><button type="submit" class="c-btn c-btn--danger" :disabled="!disband.canStart.value || uploading">解散战队</button></form>
              <CMutationError :message="disband.message.value" :uncertain="disband.uncertain.value" :pending="disband.pending.value" @retry="disband.retry" />
            </div>
          </div>
        </section>
      </div>
    </div>
  </main>
</template>
