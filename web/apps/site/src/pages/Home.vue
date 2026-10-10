<script lang="ts">
import type { LoadCtx } from "../router"

export async function load(ctx?: LoadCtx) {
  const f = ctx?.fetch ?? fetch
  const base = ctx?.apiBase ?? ""
  let home = null
  try {
    const res = await f(`${base}/api/page/home`)
    if (res.ok) {
      home = await res.json()
    }
  } catch {
    // API not reachable or error during SSR
  }
  // marker 里的 < 走真渲染，确认状态脚本把 < 转义了。页面上不显示。
  return { title: "SJTU-OW", marker: "<", home }
}
</script>
<script setup lang="ts">
import { imageUrl } from "../media"
import { inject, computed } from "vue"
import { useHead } from "@unhead/vue"
import SectionHead from "../components/SectionHead.vue"
import CSeats from "../components/CSeats.vue"
import PostCard from "../components/PostCard.vue"
import TeamTile from "../components/TeamTile.vue"
import { VIEWER, type Viewer } from "../viewer"

interface HomeData {
  stats?: {
    member_count: number
    team_count: number
    scrims_held: number
    founded_on?: string
    age?: { years: number; days: number } | null
    hero_image_id?: number | null
    qq_group_url?: string
  } | null
  feature_tournament?: {
    id: number
    title: string
    phase: string
    phase_label: string
    registration_mode: string
    takes_individuals: boolean
    approved_teams: number
    starts_at?: string
    registration_opens_at?: string
    registration_closes_at?: string
    cover_image_id?: number | null
    facts: string
  } | null
  scrims?: Array<{
    id: number
    title: string
    starts_at: string
    month: number
    day: number
    weekday: string
    time: string
    count: number
    capacity: number
    signup_open: boolean
  }> | null
  news?: Array<{
    id: number
    slug: string
    title: string
    category_name: string
    cover_image_id?: number | null
    summary: string
    reading_time: number
    author_name: string
    first_published_at?: string | null
    pinned?: boolean
  }> | null
  notices?: Array<{
    id: number
    slug: string
    title: string
    month: number
    day: number
    published_at_raw: string
  }> | null
  teams?: Array<{
    id: number
    name: string
    logo_image_id?: number | null
    member_count: number
    is_recruiting: boolean
    wanted_roles?: string
    created_at_month: string
  }> | null
}

const data = inject<{ title: string; home?: HomeData | null }>("page-data")
const viewer = inject<Viewer>(VIEWER)
useHead({ title: data?.title ?? "SJTU-OW" })

const home = computed(() => data?.home)
const stats = computed(() => home.value?.stats)
const feature = computed(() => home.value?.feature_tournament)
const scrims = computed(() => home.value?.scrims ?? [])
const news = computed(() => home.value?.news ?? [])
const notices = computed(() => home.value?.notices ?? [])
const teams = computed(() => home.value?.teams ?? [])
</script>
<template>
  <main id="main" class="flex-1">
    <!-- Hero (design 5.2, 13.2.5; v5.1) -->
    <section class="c-hero" aria-labelledby="hero-title">
      <div class="c-hero__img" aria-hidden="true"></div>
      <div class="l-container c-hero__body">
        <div class="c-hero__copy">
          <h1 id="hero-title" class="c-hero__title">
            <span>上海交通大学</span><span>守望先锋社区</span>
          </h1>
          <p class="c-hero__lede">交大玩家自己的守望先锋社区。每周内战，每学期一届校内赛事。</p>
          <div class="c-hero__actions">
            <a v-if="!viewer?.user" href="/accounts/signup/" class="c-btn c-btn--primary">加入社区</a>
            <a v-else href="/me/" class="c-btn c-btn--primary">个人中心</a>
            <a
              v-if="stats?.qq_group_url"
              :href="stats.qq_group_url"
              class="c-btn c-btn--secondary"
              rel="noopener"
              data-quick="qq"
            >加入 QQ 群</a>
          </div>
        </div>
        <div class="c-hero__emblem" aria-hidden="true">
          <span class="c-hero__emblem-body"></span>
          <span class="c-hero__emblem-gear"></span>
        </div>
      </div>
      <div class="l-container c-hero__foot">
        <dl class="c-stats" aria-label="社区数字">
          <div><dt>注册成员</dt><dd>{{ stats?.member_count ?? 0 }}</dd></div>
          <div><dt>战队</dt><dd>{{ stats?.team_count ?? 0 }}</dd></div>
          <div><dt>累计内战</dt><dd>{{ stats?.scrims_held ?? 0 }}</dd></div>
          <div v-if="stats?.age" data-figure="age">
            <dt>社区已成立</dt>
            <dd>
              <template v-if="stats.age.years">{{ stats.age.years }} 年 </template>{{ stats.age.days }} 天
            </dd>
          </div>
        </dl>
      </div>
    </section>

    <!-- 近期 (Upcoming tournaments & scrims) -->
    <section v-if="feature || scrims.length > 0" class="l-container l-section" aria-labelledby="home-upcoming">
      <SectionHead title="近期" headingId="home-upcoming" moreHref="/scrims/" moreLabel="全部内战" />
      <div class="c-upcoming c-upcoming--two">
        <!-- 焦点赛事 -->
        <article v-if="feature" class="c-feature" data-next-up="tournament" :data-phase="feature.phase">
          <img
            v-if="feature.cover_image_id"
            :src="imageUrl(feature.cover_image_id, 'fill-1280x720')"
            class="c-feature__img"
            alt=""
          />
          <img
            v-else
            :src="`/static/img/placeholders/cover-${String((feature.id % 8) + 1).padStart(2, '0')}.svg`"
            class="c-feature__img"
            alt=""
          />
          <div class="c-feature__body">
            <span v-if="feature.phase === 'open'" class="c-status c-status--live">报名中</span>
            <span v-else-if="feature.phase === 'upcoming'" class="c-status c-status--info">即将开始报名</span>
            <span v-else-if="feature.phase === 'finished'" class="c-status">已结束</span>
            <span v-else class="c-status">报名已截止</span>
            <h3 class="c-feature__title">
              <a :href="`/tournaments/${feature.id}/`" class="c-stretch">{{ feature.title }}</a>
            </h3>
            <p class="c-feature__facts">{{ feature.facts }}</p>
          </div>
        </article>

        <!-- 近期内战列表 -->
        <ol v-if="scrims.length > 0" class="c-rows">
          <li v-for="scrim in scrims" :key="scrim.id" class="c-row" data-next-up="scrim">
            <span class="c-date"><small>{{ scrim.month }}月</small><b>{{ scrim.day }}</b></span>
            <div class="c-row__main">
              <h3 class="c-row__title">
                <a :href="`/scrims/${scrim.id}/`" class="c-stretch">{{ scrim.title }}</a>
              </h3>
              <p class="c-row__meta">{{ scrim.weekday }} {{ scrim.time }} · 已报 {{ scrim.count }} / {{ scrim.capacity }}</p>
              <CSeats :taken="scrim.count" :total="scrim.capacity" />
            </div>
            <span v-if="scrim.signup_open" class="c-status c-status--live">报名中</span>
            <span v-else class="c-status">报名已截止</span>
          </li>
        </ol>
      </div>
    </section>

    <!-- 资讯与公告 -->
    <section v-if="news.length > 0 || notices.length > 0" class="l-container c-homegrid" aria-label="资讯与公告">
      <div v-if="news.length > 0" class="min-w-0">
        <SectionHead title="资讯" headingId="home-news" moreHref="/news/" moreLabel="全部资讯" />
        <div class="c-media-grid c-media-grid--two">
          <PostCard v-for="article in news" :key="article.id" :article="article" />
        </div>
      </div>
      <aside v-if="notices.length > 0" class="min-w-0" aria-labelledby="home-notices">
        <SectionHead title="公告" headingId="home-notices" moreHref="/news/?category=notice" moreLabel="全部公告" />
        <ol class="c-rows">
          <li v-for="notice in notices" :key="notice.id" class="c-row">
            <time class="c-date" :datetime="notice.published_at_raw">
              <small>{{ notice.month }}月</small><b>{{ notice.day }}</b>
            </time>
            <div class="c-row__main">
              <h3 class="c-row__title">
                <a :href="`/news/${notice.slug}/`" class="c-stretch">{{ notice.title }}</a>
              </h3>
            </div>
          </li>
        </ol>
      </aside>
    </section>

    <!-- 活跃战队 -->
    <section v-if="teams.length > 0" class="l-container l-section" aria-labelledby="home-teams">
      <SectionHead
        title="战队"
        headingId="home-teams"
        moreHref="/teams/"
        :moreLabel="stats?.team_count ? `全部 ${stats.team_count} 支战队` : '全部战队'"
      />
      <ul class="c-teams c-teams--six">
        <TeamTile v-for="team in teams" :key="team.id" :team="team" />
      </ul>
    </section>
  </main>
</template>
