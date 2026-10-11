<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiTeamsId } from "@sjtu-ow/api"
import { requireTeam } from "../team-domain"

export async function load(ctx: LoadCtx) {
  const detail = await getApiTeamsId(ctx.api, ctx.params.id)
  const team = requireTeam(detail.team)
  return { title: team.name, detail, team }
}
</script>

<script setup lang="ts">
import { computed, inject } from "vue"
import { useHead } from "@unhead/vue"
import { imageUrl } from "@sjtu-ow/shared/media"
import { initial, hue } from "@sjtu-ow/shared/initial"
import { owDate } from "@sjtu-ow/shared/time"
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import TeamJoin from "../components/TeamJoin.vue"
import TeamRoster from "../components/TeamRoster.vue"
import TeamAlumniList from "../components/TeamAlumniList.vue"
import { requirePageData } from "../personal"
import { teamRoleLabels, teamScene } from "../team-domain"
import type { Team, TeamDetail } from "../team-domain"

const data = requirePageData(inject<{ team: Team; detail: TeamDetail }>("page-data"))
const team = computed(() => data.team)
const detail = computed(() => data.detail)
const captain = computed(() => detail.value.members.find((member) => member.role === "captain"))
const wanted = computed(() => teamRoleLabels(team.value.recruiting_roles))
const disbanded = computed(() => Boolean(team.value.disbanded_at))
useHead(computed(() => ({ title: `${team.value.name} · 战队 · SJTU-OW` })))
</script>

<template>
  <main id="main" class="flex-1">
    <header class="c-stage c-stage--team">
      <img class="c-stage__img" :src="teamScene(team.id)" width="1600" height="900" alt="">
      <div class="l-container l-container--narrow c-stage__body">
        <nav class="c-crumbs" aria-label="位置">
          <a href="/">首页</a><span class="c-crumbs__sep">/</span>
          <a href="/teams/">战队</a><span class="c-crumbs__sep">/</span><span>{{ team.name }}</span>
        </nav>
        <div class="c-stage__team">
          <span :class="'c-teams__logo c-teams__logo--lg c-hue-' + hue(team.id)">
            <img v-if="team.logo_image_id" :src="imageUrl(team.logo_image_id, 'fill-288x288')" :alt="team.name">
            <template v-else>{{ initial(team.name) }}</template>
          </span>
          <div class="min-w-0">
            <p class="c-stage__tags">
              <span v-if="disbanded" class="c-status">已解散</span>
              <template v-else-if="team.is_recruiting">
                <span class="c-status c-status--live">招募中</span>
                <span v-if="wanted" class="c-stage__wanted">缺 {{ wanted }}</span>
              </template>
              <span v-else class="c-status">暂不招募</span>
            </p>
            <h1 class="c-stage__title">{{ team.name }}</h1>
            <dl class="c-stage__facts">
              <div v-if="captain"><dt>队长</dt><dd>{{ captain.nickname }}<template v-if="!captain.is_active">（账号已停用）</template></dd></div>
              <div><dt>现役</dt><dd>{{ detail.members.length }} / {{ detail.max_members }} 人</dd></div>
              <div v-if="detail.entries"><dt>参赛</dt><dd>{{ detail.entries.length }} 次</dd></div>
              <div><dt>成立</dt><dd><time :datetime="team.created_at">{{ owDate(new Date(team.created_at)) }}</time></dd></div>
            </dl>
          </div>
        </div>
      </div>
    </header>
    <div class="l-container l-container--narrow l-section">
      <div v-if="disbanded" class="c-notice c-notice--warn mb-10" role="status">
        <CIcon name="alert" /><div class="c-notice__body">该战队已解散。</div>
      </div>
      <div class="l-split">
        <div class="flex min-w-0 flex-col gap-12">
          <section v-if="!disbanded" class="c-panel" aria-label="加入"><TeamJoin :team="team" :viewer="detail.viewer" /></section>
          <section v-if="team.description" aria-labelledby="team-about">
            <SectionHead title="简介" heading-id="team-about" />
            <p class="l-prose whitespace-pre-line leading-8">{{ team.description }}</p>
          </section>
          <TeamRoster :members="detail.members" />
          <TeamAlumniList :alumni="detail.alumni" />
          <section v-if="detail.entries" aria-labelledby="team-record">
            <SectionHead title="参赛记录" heading-id="team-record" />
            <table v-if="detail.entries.length" class="c-table">
              <thead><tr><th scope="col">赛事</th><th scope="col" class="is-num">状态</th></tr></thead>
              <tbody>
                <tr v-for="entry in detail.entries" :key="entry.id" data-team-entry>
                  <td><a :href="'/tournaments/' + entry.tournament_id + '/'" class="font-semibold hover:text-primary-text">{{ entry.title }}</a></td>
                  <td class="is-num"><span :class="entry.status === 'cancelled' || entry.status === 'finished' ? 'c-status' : 'c-status c-status--ok'">{{ entry.status === 'cancelled' ? '已取消' : entry.status === 'finished' ? '已结束' : '已通过' }}</span></td>
                </tr>
              </tbody>
            </table>
            <p v-else class="text-fg-2">还没有通过审核的赛事报名。</p>
          </section>
        </div>
        <aside>
          <dl class="c-facts c-panel">
            <dt>队长</dt><dd>{{ captain?.nickname ?? '—' }}</dd>
            <dt>成立</dt><dd class="font-numeric">{{ owDate(new Date(team.created_at)) }}</dd>
            <dt>现役</dt><dd class="font-numeric">{{ detail.members.length }} / {{ detail.max_members }}</dd>
            <dt>招募</dt><dd>{{ team.is_recruiting && !disbanded ? '招募中' : '暂不招募' }}</dd>
            <template v-if="wanted && !disbanded"><dt>缺的位置</dt><dd>{{ wanted }}</dd></template>
            <template v-if="detail.alumni.length"><dt>退役</dt><dd class="font-numeric">{{ detail.alumni.length }} 人</dd></template>
          </dl>
        </aside>
      </div>
    </div>
  </main>
</template>
