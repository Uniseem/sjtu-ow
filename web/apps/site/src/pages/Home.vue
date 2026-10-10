<script lang="ts">
import { getApiMeAgenda, getApiPageHome, type GetApiPageHomeOut } from "@sjtu-ow/api"
import type { LoadCtx } from "../router"
import type { ArticleCard } from "../pending-api"

// content/templates/content/home_page.html (design 5.2, 13.2.5): full-screen
// hero, the figures along its bottom edge, 近期 (the big card on the left and
// the scrims on the right; whichever is missing leaves the page's ground),
// news and notices, teams — and 我的安排 for a signed-in member, empty for a
// visitor. The stats block can be null before the site is set up (v6.48).
export async function load(ctx: LoadCtx) {
  const home: GetApiPageHomeOut = await getApiPageHome(ctx.api)
  const member = (await ctx.viewer()).user
  // The agenda is its own resource endpoint today (glm-handoff 5.1 wants it
  // combined into HomePageOut eventually); one fixed extra request while
  // signed in, like the article page's comments.
  const agenda = member ? (await getApiMeAgenda(ctx.api)).items : []
  // marker 里的 < 走真渲染，确认状态脚本把 < 转义了。页面上不显示。
  return { title: "首页", marker: "<", home, agenda }
}
</script>
<script setup lang="ts">
import { computed, inject } from "vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CPagehead from "@sjtu-ow/ui/CPagehead.vue"
import CSeats from "@sjtu-ow/ui/CSeats.vue"
import PostCard from "@sjtu-ow/ui/PostCard.vue"
import TeamTile from "@sjtu-ow/ui/TeamTile.vue"
import SectionHead from "../components/SectionHead.vue"
import { imageUrl } from "../media"
import { owMonthNum, owDay, owTime, owWeekday, owISO } from "@sjtu-ow/shared/time"
import { usePageMeta } from "../meta"
import type { ArticleCard } from "../pending-api"
import { VIEWER } from "../viewer"

// The page-data object sheds the previous page's keys on navigation before
// the old component unmounts, so everything reads optional (StandardPage).
const data = inject<{ title: string; home?: GetApiPageHomeOut; agenda?: { kind: string; title: string; url: string; when: string | null; note: string }[] }>("page-data")
const viewer = inject(VIEWER, { user: null })
// The old home page is a Wagtail page titled 首页 (build_seo: 页面 · SJTU-OW).
usePageMeta(() => ({ title: data?.title ?? "首页" }))

const home = computed(() => data?.home)
const stats = computed(() => home.value?.stats)
const feature = computed(() => home.value?.feature_tournament)
const scrims = computed(() => home.value?.scrims ?? [])
const news = computed(() => (home.value?.news ?? []) as ArticleCard[])
const notices = computed(() => home.value?.notices ?? [])
const teams = computed(() => home.value?.teams ?? [])
const agenda = computed(() => data?.agenda ?? [])

function featureCover(): string {
  const t = feature.value
  if (!t) return ""
  if (t.cover_image_id) return imageUrl(t.cover_image_id, "fill-1280x720")
  if ((t as { default_cover_image_id?: number | null }).default_cover_image_id) return imageUrl((t as { default_cover_image_id: number }).default_cover_image_id, "fill-1280x720")
  return `/static/img/placeholders/cover-${String(((t.id + 13) % 36) + 1).padStart(2, "0")}.svg`
}
</script>
<template>
  <main id="main" class="flex-1">
    <!-- Hero (design 5.2, 13.2.5; v5.1): a picture behind (首屏图片, else the
         moving placeholder scene, by day or at night with the mode), veiled
         in the page's ground most on the left; the emblem's gear ring turns
         slowly, CSS only. -->
    <section class="c-hero" aria-labelledby="hero-title">
      <CPagehead section="home" :image-id="stats?.hero_image_id" image-class="c-hero__img" />
      <div class="l-container c-hero__body">
        <div class="c-hero__copy">
          <h1 id="hero-title" class="c-hero__title"><span>上海交通大学</span><span>守望先锋社区</span></h1>
          <p class="c-hero__lede">交大玩家自己的守望先锋社区。每周内战，每学期一届校内赛事。</p>
          <div class="c-hero__actions">
            <a href="/accounts/signup/" class="c-btn c-btn--primary">加入社区</a>
            <a v-if="stats?.qq_group_url" :href="stats.qq_group_url" class="c-btn c-btn--secondary" rel="noopener" data-quick="qq">加入 QQ 群</a>
          </div>
        </div>
        <div class="c-hero__emblem" aria-hidden="true"><span class="c-hero__emblem-body"></span><span class="c-hero__emblem-gear"></span></div>
      </div>
      <div class="l-container c-hero__foot">
        <dl class="c-stats" aria-label="社区数字">
          <div><dt>注册成员</dt><dd>{{ stats?.member_count ?? 0 }}</dd></div>
          <div><dt>战队</dt><dd>{{ stats?.team_count ?? 0 }}</dd></div>
          <div><dt>累计内战</dt><dd>{{ stats?.scrims_held ?? 0 }}</dd></div>
          <div v-if="stats?.age" data-figure="age">
            <dt>社区已成立</dt>
            <dd><template v-if="stats.age.years">{{ stats.age.years }} 年 </template>{{ stats.age.days }} 天</dd>
          </div>
        </dl>
      </div>
    </section>

    <section class="l-container l-section" aria-labelledby="home-upcoming">
      <div class="c-sectionhead">
        <h2 id="home-upcoming">近期</h2>
        <a href="/scrims/" class="c-btn c-btn--quiet">全部内战<CIcon name="arrow-right" /></a>
      </div>
      <!-- 我的安排 (design 5.2, v6.48): empty for a visitor. -->
      <div id="slot-my-agenda" data-slot="my-agenda">
        <div v-if="viewer.user" class="c-panel mb-8" data-my-agenda>
          <h3 class="mb-3 font-semibold">我的安排</h3>
          <ol v-if="agenda.length" class="c-rows">
            <li v-for="item in agenda" :key="item.url + item.title" class="c-row px-0" data-agenda-item>
              <span v-if="item.when" class="c-date"><small>{{ owMonthNum(new Date(item.when)) }}月</small><b>{{ owDay(new Date(item.when)) }}</b></span>
              <span v-else class="c-date"><small>时间</small><b>未定</b></span>
              <div class="c-row__main">
                <p class="c-row__title"><a :href="item.url" class="c-stretch">{{ item.title }}</a></p>
                <p class="c-row__meta">{{ item.kind }}<template v-if="item.when"> · {{ owWeekday(new Date(item.when)) }} {{ owTime(new Date(item.when)) }}</template><template v-else> · 时间未定</template> · {{ item.note }}</p>
              </div>
            </li>
          </ol>
          <p v-else class="text-fg-2" data-agenda-empty>接下来没有报名的活动。看看<a href="/tournaments/" class="c-link">赛事</a>和<a href="/scrims/" class="c-link">内战</a>。</p>
        </div>
      </div>
      <!-- 近期 (design 5.2, v6.66/v6.68): always the big card on the left and
           the scrims on the right; whichever is missing leaves the ground. -->
      <div class="c-upcoming c-upcoming--two">
        <article v-if="feature" class="c-feature" data-next-up="tournament" :data-phase="feature.phase">
          <img :src="featureCover()" class="c-feature__img" alt="" width="1280" height="720">
          <div class="c-feature__body">
            <span v-if="feature.phase === 'open'" class="c-status c-status--live">报名中</span>
            <span v-else-if="feature.phase === 'upcoming'" class="c-status c-status--info">即将开始报名</span>
            <span v-else-if="feature.phase === 'finished'" class="c-status">已结束</span>
            <span v-else class="c-status">报名已截止</span>
            <h3 class="c-feature__title"><a :href="`/tournaments/${feature.id}/`" class="c-stretch">{{ feature.title }}</a></h3>
            <p class="c-feature__facts">{{ feature.facts }}</p>
          </div>
        </article>
        <ol v-if="scrims.length" class="c-rows">
          <li v-for="scrim in scrims" :key="scrim.id" class="c-row" data-next-up="scrim">
            <span class="c-date"><small>{{ scrim.month }}月</small><b>{{ scrim.day }}</b></span>
            <div class="c-row__main">
              <h3 class="c-row__title"><a :href="`/scrims/${scrim.id}/`" class="c-stretch">{{ scrim.title }}</a></h3>
              <p class="c-row__meta">{{ scrim.weekday }} {{ scrim.time }} · 已报 {{ scrim.count }} / {{ scrim.capacity }}</p>
              <CSeats :taken="scrim.count" :total="scrim.capacity" />
            </div>
            <span v-if="scrim.signup_open" class="c-status c-status--live">报名中</span>
            <span v-else class="c-status">报名已截止</span>
          </li>
        </ol>
      </div>
    </section>

    <section class="l-container c-homegrid" aria-label="资讯与公告">
      <div class="min-w-0">
        <div class="c-sectionhead">
          <h2 id="home-news">资讯</h2>
          <a href="/news/" class="c-btn c-btn--quiet">全部资讯<CIcon name="arrow-right" /></a>
        </div>
        <div class="c-media-grid c-media-grid--two">
          <PostCard v-for="article in news" :key="article.id" :article="article" />
        </div>
      </div>

      <aside class="min-w-0" aria-labelledby="home-notices">
        <div class="c-sectionhead">
          <h2 id="home-notices">公告</h2>
          <a href="/news/?category=notice" class="c-btn c-btn--quiet">全部公告<CIcon name="arrow-right" /></a>
        </div>
        <ol v-if="notices.length" class="c-rows">
          <li v-for="notice in notices" :key="notice.id" class="c-row">
            <time class="c-date" :datetime="notice.published_at_raw ? owISO(new Date(notice.published_at_raw)) : undefined"><small>{{ notice.month }}月</small><b>{{ notice.day }}</b></time>
            <div class="c-row__main">
              <h3 class="c-row__title"><a :href="`/news/${notice.slug}/`" class="c-stretch">{{ notice.title }}</a></h3>
            </div>
          </li>
        </ol>
      </aside>
    </section>

    <section class="l-container l-section" aria-labelledby="home-teams">
      <div class="c-sectionhead">
        <h2 id="home-teams">战队</h2>
        <a href="/teams/" class="c-btn c-btn--quiet">{{ stats?.team_count ? `全部 ${stats.team_count} 支战队` : "全部战队" }}<CIcon name="arrow-right" /></a>
      </div>
      <ul v-if="teams.length" class="c-teams c-teams--six">
        <TeamTile v-for="team in teams" :key="team.id" :team="team" />
      </ul>
    </section>
  </main>
</template>
