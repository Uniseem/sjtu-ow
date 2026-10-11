<script lang="ts">
import type { LoadCtx } from "../router"
import { getTeamCreateState } from "../team-editor"
export async function load(ctx: LoadCtx) { return { title: "创建战队", state: await getTeamCreateState(ctx.api) } }
</script>
<script setup lang="ts">
import { inject, reactive, ref } from "vue"
import { useHead } from "@unhead/vue"
import { postApiTeams } from "@sjtu-ow/api"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import TeamLogoUpload from "../components/TeamLogoUpload.vue"
import TeamFields from "../components/TeamFields.vue"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import { requirePageData } from "../personal"
import { finishAccountAction } from "../account-form"
import type { TeamCreateState, TeamValues } from "../team-editor"
const data = requirePageData(inject<{ state: TeamCreateState }>("page-data"))
const api = useApi()
const uploading = ref(false)
const values = reactive<TeamValues>({ name: "", description: "", is_recruiting: true, recruiting_roles: [], member_contact: "", logo_image_id: null, remove_logo: false })
const create = useMutation((body: Pick<TeamValues, "name" | "description" | "is_recruiting" | "recruiting_roles" | "logo_image_id">, extras) => postApiTeams(api, body, extras), result => {
  if (!result.team) throw new Error("创建结果无效，请重新打开我的战队确认。")
  return finishAccountAction("/teams/" + result.team.id + "/")
})
useHead({ title: "创建战队 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })
function submit(): void {
  if (!data.state.can_create) return
  void create.submit({ name: values.name, description: values.description, is_recruiting: values.is_recruiting, recruiting_roles: [...values.recruiting_roles], logo_image_id: values.logo_image_id })
}
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead">
      <div class="l-container l-container--narrow">
        <nav class="c-crumbs" aria-label="位置"><a href="/">首页</a><span class="c-crumbs__sep">/</span><a href="/teams/">战队</a><span class="c-crumbs__sep">/</span><span>创建战队</span></nav>
        <h1>创建战队</h1>
        <p class="c-pagehead__lede">你会自动成为队长。每人最多同时担任 <span class="font-numeric">{{ data.state.max_captained }}</span> 支战队的队长。</p>
      </div>
    </header>
    <div class="l-container l-container--narrow pt-8 pb-16 lg:pb-24">
      <div v-if="!data.state.can_create" class="c-notice c-notice--warning max-w-2xl" role="status">
        <CIcon name="alert" /><div class="c-notice__body"><p>{{ data.state.blocker }}</p><p class="mt-2"><a href="/me/teams/">回到我的战队</a></p></div>
      </div>
      <form v-else method="post" enctype="multipart/form-data" class="c-form max-w-xl" :aria-busy="create.pending.value || undefined" @submit.prevent="submit">
        <CMutationError :message="create.message.value" :uncertain="create.uncertain.value" :pending="create.pending.value" @retry="create.retry" />
        <TeamFields :values="values" :fields="create.fields.value" :disabled="create.pending.value || create.uncertain.value" create @text="(name, value) => values[name] = value" @choice="changes => Object.assign(values, changes)" />
        <TeamLogoUpload :image-id="values.logo_image_id" :disabled="create.pending.value || create.uncertain.value" @changed="id => values.logo_image_id = id" @busy="value => uploading = value" />
        <div class="c-formbar"><button type="submit" class="c-btn c-btn--primary" :disabled="!create.canStart.value || uploading">创建</button><a href="/teams/" class="c-btn c-btn--quiet">取消</a></div>
      </form>
    </div>
  </main>
</template>
