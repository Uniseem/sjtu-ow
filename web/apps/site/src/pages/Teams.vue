<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiTeams } from "@sjtu-ow/api"
import { validTeamRole } from "../team-domain"

export async function load(ctx: LoadCtx) {
  const role = validTeamRole(ctx.query.role ?? "")
  const list = await getApiTeams(ctx.api, {
    recruiting: ctx.query.recruiting === "1",
    role: role || undefined,
  })
  return { title: "战队", list }
}
</script>

<script setup lang="ts">
import { computed, inject } from "vue"
import { useHead } from "@unhead/vue"
import CPagehead from "@sjtu-ow/ui/CPagehead.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import TeamTile from "@sjtu-ow/ui/TeamTile.vue"
import { requirePageData } from "../personal"
import { TEAM_ROLES, teamRoleLabel } from "../team-domain"
import type { TeamList } from "../team-domain"

const data = requirePageData(inject<{ list: TeamList }>("page-data"))
const list = computed(() => data.list)
const emptyTitle = computed(() => list.value.role
  ? `暂时没有缺${teamRoleLabel(list.value.role)}的战队`
  : "还没有战队")
const emptyMessage = computed(() => list.value.role
  ? "现在招募中的战队都不缺这个位置，或者已经满员。可以看看全部战队，或者自己建一支。"
  : "第一支战队可以由你来建。")
useHead({ title: "战队 · SJTU-OW" })
</script>

<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead c-pagehead--picture">
      <CPagehead section="teams" :image-id="list.banner_image_id" />
      <div class="l-container">
        <div class="c-pagehead__row">
          <div>
            <h1>战队</h1>
            <p class="c-pagehead__lede">社团里的固定队伍，每队最多 {{ list.max_members }} 人。找一支招募中的申请加入，或者自己建一支。</p>
          </div>
          <div class="c-pagehead__actions">
            <a href="/teams/new/" class="c-btn c-btn--primary"><CIcon name="plus" />创建战队</a>
          </div>
        </div>
        <nav class="c-tabs mt-8" aria-label="筛选">
          <a href="/teams/" :aria-current="!list.recruiting_only && !list.role ? 'page' : undefined">全部<span class="c-tabs__count">{{ list.team_total }}</span></a>
          <a href="/teams/?recruiting=1" :aria-current="list.recruiting_only ? 'page' : undefined">只看招募中<span class="c-tabs__count">{{ list.recruiting_total }}</span></a>
          <a
            v-for="role in TEAM_ROLES"
            :key="role.code"
            :href="'/teams/?role=' + role.code"
            :aria-current="list.role === role.code ? 'page' : undefined"
            :data-role-tab="role.code"
          >缺{{ role.label }}<span class="c-tabs__count">{{ list.role_counts[role.code] ?? 0 }}</span></a>
        </nav>
      </div>
    </header>
    <div class="l-container pt-10 pb-16 lg:pt-14 lg:pb-24">
      <ul v-if="list.teams.length" class="c-teams c-teams--list">
        <TeamTile
          v-for="team in list.teams"
          :key="team.id"
          :team="team"
          :capacity="list.max_members"
          :members="team.member_count"
          show-closed
          about
        />
      </ul>
      <CEmpty v-else :title="emptyTitle" :message="emptyMessage" action-url="/teams/new/" action-label="创建战队" />
    </div>
  </main>
</template>
