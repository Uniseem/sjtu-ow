<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiTeamsId } from "@sjtu-ow/api"
import { requireTeam } from "../team-domain"

export async function load(ctx: LoadCtx) {
  const detail = await getApiTeamsId(ctx.api, ctx.params.id)
  const team = requireTeam(detail.team)
  return { title: `申请加入 ${team.name}`, team, viewer: detail.viewer }
}
</script>

<script setup lang="ts">
import { computed, inject, ref } from "vue"
import { useHead } from "@unhead/vue"
import { postApiTeamsIdApplications } from "@sjtu-ow/api"
import CField from "@sjtu-ow/ui/CField.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import { requirePageData } from "../personal"
import { finishAccountAction } from "../account-form"
import { TEAM_ROLES } from "../team-domain"
import type { Team, TeamDetail } from "../team-domain"

const data = requirePageData(inject<{ team: Team; viewer: TeamDetail["viewer"] }>("page-data"))
const api = useApi()
const roles = ref<string[]>([])
const message = ref("")
const title = computed(() => `申请加入 ${data.team.name} · SJTU-OW`)
const mutation = useMutation(
  (body: { roles: string[]; message: string }, extras) => postApiTeamsIdApplications(api, data.team.id, body, extras),
  () => finishAccountAction(`/teams/${data.team.id}/`),
)
useHead(computed(() => ({ title: title.value, meta: [{ name: "robots", content: "noindex" }] })))

function apply(): void {
  if (!data.viewer.can_apply) return
  void mutation.submit({ roles: [...roles.value], message: message.value.trim() })
}
</script>

<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead">
      <div class="l-container l-container--narrow">
        <nav class="c-crumbs" aria-label="位置">
          <a href="/">首页</a><span class="c-crumbs__sep">/</span>
          <a href="/teams/">战队</a><span class="c-crumbs__sep">/</span>
          <a :href="'/teams/' + data.team.id + '/'">{{ data.team.name }}</a><span class="c-crumbs__sep">/</span><span>申请加入</span>
        </nav>
        <h1>申请加入「{{ data.team.name }}」</h1>
        <p class="c-pagehead__lede">队长会看到你的昵称、意向位置、留言和游戏 ID，通过后你就是队员了。</p>
      </div>
    </header>
    <div class="l-container l-container--narrow pt-8 pb-16 lg:pb-24">
      <template v-if="!data.viewer.can_apply">
        <div class="c-notice c-notice--warn max-w-xl" role="status">
          <CIcon name="alert" /><div class="c-notice__body">
            <p>{{ data.viewer.apply_reason }}</p>
            <a v-if="data.viewer.needs_game_account" href="/me/game-accounts/" class="c-link">补全游戏 ID</a>
          </div>
        </div>
        <p class="mt-6"><a :href="'/teams/' + data.team.id + '/'" class="c-btn c-btn--secondary">返回战队主页</a></p>
      </template>
      <form v-else method="post" class="c-form max-w-xl" :aria-busy="mutation.pending.value || undefined" @submit.prevent="apply">
        <CMutationError :message="Object.keys(mutation.fields.value).length ? '' : mutation.message.value" :uncertain="mutation.uncertain.value" :pending="mutation.pending.value" @retry="mutation.retry" />
        <CField v-for="role in TEAM_ROLES" :key="role.code" :label="role.label" kind="checkbox" :input-id="'id_role_' + role.code" :errors="mutation.fields.value['role_' + role.code]">
          <input :id="'id_role_' + role.code" v-model="roles" type="checkbox" :name="'role_' + role.code" :value="role.code" :disabled="mutation.pending.value || mutation.uncertain.value">
        </CField>
        <CField label="留言" input-id="id_message" :errors="mutation.fields.value.message">
          <textarea id="id_message" v-model="message" name="message" rows="3" maxlength="200" aria-describedby="id_message_helptext" :disabled="mutation.pending.value || mutation.uncertain.value" />
          <template #help><span id="id_message_helptext">最多 200 字。提交申请后，队长可以看到你的游戏 ID 和段位。</span></template>
        </CField>
        <div class="c-formbar">
          <button type="submit" class="c-btn c-btn--primary" :disabled="!mutation.canStart.value">提交申请</button>
          <a :href="'/teams/' + data.team.id + '/'" class="c-btn c-btn--quiet">取消</a>
        </div>
      </form>
    </div>
  </main>
</template>
