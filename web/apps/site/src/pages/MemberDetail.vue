<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiMembersId } from "@sjtu-ow/api"
export async function load(ctx: LoadCtx) {
  const page = await getApiMembersId(ctx.api, ctx.params.id)
  return { title: page.card.nickname, page }
}
</script>
<script setup lang="ts">
import { computed, inject } from "vue"
import { useHead } from "@unhead/vue"
import { imageUrl } from "@sjtu-ow/shared/media"
import { hue, initial } from "@sjtu-ow/shared/initial"
import { owDate, owDay, owMonthNum } from "@sjtu-ow/shared/time"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"

import { requirePageData } from "../personal"
import { memberPlay, type MemberPage } from "../member-domain"
import { teamScene, joinedMonth } from "../team-domain"
const data = requirePageData(inject<{ page: MemberPage }>("page-data"))
const member = computed(() => data.page.card)
const play = computed(() => memberPlay(member.value))
const face = computed(() => member.value.avatar_image_id || member.value.default_avatar_image_id)
useHead(computed(() => ({ title: member.value.nickname + " · 成员 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })))
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-stage c-stage--team" data-member-head>
      <img class="c-stage__img" :src="teamScene(member.user_id)" width="1600" height="900" alt="">
      <div class="l-container l-container--narrow c-stage__body">
        <nav class="c-crumbs" aria-label="位置"><a href="/">首页</a><span class="c-crumbs__sep">/</span><a href="/members/">成员</a><span class="c-crumbs__sep">/</span><span>{{ member.nickname }}</span></nav>
        <div class="c-stage__team">
          <span :class="['c-teams__logo', 'c-teams__logo--lg', 'c-hue-' + hue(member.user_id)]">
            <img v-if="face" :src="imageUrl(face, 'fill-288x288')" :alt="member.nickname">
            <template v-else>{{ initial(member.nickname) }}</template>
          </span>
          <div class="min-w-0">
            <dl v-if="data.page.groups.length" class="c-stage__tags" data-member-groups>
              <div v-for="group in data.page.groups" :key="group.id" class="flex flex-wrap items-center gap-1.5">
                <dt class="c-stage__wanted">{{ group.name }}</dt>
                <dd v-for="(title, index) in group.titles" :key="index" class="c-tag">{{ title }}</dd>
              </div>
            </dl>
            <h1 class="c-stage__title">{{ member.nickname }}</h1>
            <p v-if="member.motto" class="c-stage__lede" data-motto>“{{ member.motto }}”</p>
            <dl class="c-stage__facts" data-member-facts>
              <div v-if="play.roles.length"><dt>常用位置</dt><dd>{{ play.is_flex ? '全能' : play.roles.map(role => role.label).join('、') }}</dd></div>
              <div v-if="play.main_rank"><dt>{{ play.main_rank.role_label }}段位</dt><dd :class="{ 'is-stale': play.main_rank.stale }">{{ play.main_rank.label }}</dd></div>
              <div><dt>现役战队</dt><dd>{{ data.page.teams.length }} 支</dd></div>
              <div><dt>文章</dt><dd>{{ data.page.article_count }} 篇</dd></div>
            </dl>
          </div>
        </div>
      </div>
    </header>
    <div class="l-container l-container--narrow pt-10 pb-16 lg:pt-14 lg:pb-24">
      <div class="flex flex-col gap-14">
        <section v-if="data.page.is_owner" class="c-panel flex flex-col gap-3" aria-label="这是你的主页" data-owner-panel>
          <p class="flex flex-wrap items-center gap-3"><span class="text-sm text-fg-2">这是你的主页，别人看到的就是这样。</span><a href="/me/" class="c-btn c-btn--secondary c-btn--sm" data-owner-edit><CIcon name="settings" />编辑资料</a></p>
          <p v-if="!member.motto" class="text-sm text-fg-2" data-owner-hint>还没写个人宣言，<a href="/me/" class="c-link">写一句</a>（只有你看得到这句提示）。</p>
          <p v-if="!member.roles.length" class="text-sm text-fg-2" data-owner-hint>还没选常用位置，<a href="/me/" class="c-link">去选</a>。</p>
        </section>
        <section aria-labelledby="member-teams" data-member-teams>
          <SectionHead title="所在战队" heading-id="member-teams" />
          <ol v-if="data.page.teams.length" class="c-rows">
            <li v-for="team in data.page.teams" :key="team.id" class="c-row" data-member-team>
              <span :class="['c-avatar', 'c-avatar--md', 'c-hue-' + hue(team.id)]" aria-hidden="true"><img v-if="team.logo_image_id" :src="imageUrl(team.logo_image_id, 'fill-96x96')" alt="" loading="lazy"><template v-else>{{ initial(team.name) }}</template></span>
              <div class="c-row__main">
                <h3 class="c-row__title"><a :href="'/teams/' + team.id + '/'" class="c-stretch">{{ team.name }}</a></h3>
                <p class="c-row__meta"><span class="font-numeric">{{ team.member_count }}</span> 人<template v-if="team.is_recruiting !== undefined"> · {{ team.is_recruiting ? '招募中' : '暂不招募' }}</template></p>
              </div>
            </li>
          </ol>
          <p v-else class="text-fg-2">现在没有加入战队。<a v-if="data.page.is_owner" href="/teams/" class="c-link" data-owner-hint>去找一支招募中的</a></p>
        </section>
        <section v-if="data.page.alumni.length" aria-labelledby="member-alumni" data-member-alumni>
          <SectionHead title="待过的战队" heading-id="member-alumni" />
          <ol class="c-rows">
            <li v-for="(record, index) in data.page.alumni" :key="index" class="c-row">
              <span :class="['c-avatar', 'c-avatar--md', 'c-hue-' + hue(record.team_id)]" aria-hidden="true">{{ initial(record.team_name) }}</span>
              <div class="c-row__main">
                <h3 class="c-row__title"><a :href="'/teams/' + record.team_id + '/'" class="c-stretch">{{ record.team_name }}</a></h3>
                <p class="c-row__meta"><template v-if="record.joined_at"><time :datetime="record.joined_at">{{ joinedMonth(record.joined_at) }}</time> – </template><time :datetime="record.left_at">{{ joinedMonth(record.left_at) }}</time></p>
              </div>
            </li>
          </ol>
        </section>
        <section v-if="data.page.articles.length" aria-labelledby="member-articles" data-member-articles>
          <div class="c-sectionhead"><h2 id="member-articles">发表的文章</h2><span class="text-fg-3">共 <span class="font-numeric">{{ data.page.article_count }}</span> 篇</span></div>
          <ol class="c-rows">
            <li v-for="article in data.page.articles" :key="article.id" class="c-row">
              <time v-if="article.first_published_at" class="c-date" :datetime="article.first_published_at"><small>{{ owMonthNum(new Date(article.first_published_at)) }}月</small><b>{{ owDay(new Date(article.first_published_at)) }}</b></time>
              <div class="c-row__main">
                <h3 class="c-row__title"><a :href="'/news/' + article.slug + '/'" class="c-stretch">{{ article.title }}</a></h3>
                <p v-if="article.first_published_at" class="c-row__meta font-numeric">{{ owDate(new Date(article.first_published_at)) }}</p>
              </div>
            </li>
          </ol>
        </section>
      </div>
    </div>
  </main>
</template>
