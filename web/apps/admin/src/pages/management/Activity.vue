<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiAdminActivity } from "@sjtu-ow/api"
import { shanghaiParts } from "@sjtu-ow/shared/time"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import { text, date, localHref } from "./format"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const start = ref(text(route.query.start))
const end = ref(text(route.query.end))
const resource = useResource(() => route.fullPath, signal => getApiAdminActivity(api, { preset: text(route.query.preset), start: text(route.query.start), end: text(route.query.end) }, { signal }))
watch(resource.data, value => { if (value) { start.value = value.period.start.slice(0, 10); end.value = value.period.end.slice(0, 10) } })
const presets = computed(() => {
 const now = shanghaiParts(new Date())
 const year = Number(now.year) - (Number(now.month) < 9 ? 1 : 0)
 const recent = new Date(Date.UTC(Number(now.year), Number(now.month)-1, Number(now.day)-29))
 return [
 { label: '本学年', start: `${year}-09-01`, end: `${now.year}-${now.month}-${now.day}` },
 { label: '上学年', start: `${year-1}-09-01`, end: `${year}-08-31` },
 { label: '近 30 天', start: recent.toISOString().slice(0,10), end: `${now.year}-${now.month}-${now.day}` },
 ]
})
function filter() { void router.push({ path: route.path, query: { start: start.value, end: end.value } }) }
function longDay(value:string) { const p=shanghaiParts(new Date(value)); return `${p.year} 年 ${Number(p.month)} 月 ${Number(p.day)} 日` }
</script>
<template>
  <AdminPage title="活动数据" section="数据">
    <p class="b-section__text">只数已发布和已结束的内战、赛事，草稿和已取消的不算；人数按在用、验证过邮箱的成员去重。这里是活动数据，网站不做访问统计。</p>
    <form method="get" class="b-filters" data-activity-period @submit.prevent="filter">
      <RouterLink v-for="preset in presets" :key="preset.label" :to="{ path: route.path, query: { start: preset.start, end: preset.end } }" class="c-btn c-btn--secondary c-btn--sm">{{ preset.label }}</RouterLink>
      <label class="b-count" for="activity-start">从</label><input id="activity-start" v-model="start" type="date" name="start" required class="c-input" />
      <label class="b-count" for="activity-end">到</label><input id="activity-end" v-model="end" type="date" name="end" required class="c-input" />
      <button type="submit" class="c-btn c-btn--primary c-btn--sm">查看</button>
    </form>
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <template v-if="resource.data.value">
      <div v-if="resource.data.value.notice" class="c-notice c-notice--warn" data-activity-error><CIcon name="alert" /><div class="c-notice__body">{{ resource.data.value.notice }}</div></div>
      <section class="b-section">
        <h2 class="b-section__title">{{ longDay(resource.data.value.period.start) }} – {{ longDay(resource.data.value.period.end) }}</h2>
        <dl class="b-kv" data-activity-totals>
          <dt>新成员</dt><dd>{{ resource.data.value.totals.members }} 人（其中交大 {{ resource.data.value.totals.sjtu_members }} 人）</dd>
          <dt>内战</dt><dd>{{ resource.data.value.totals.scrims }} 场 · 报名 {{ resource.data.value.totals.scrim_signups }} 人次 · 上场 {{ resource.data.value.totals.scrim_players }} 人次 · 参与 {{ resource.data.value.totals.scrim_people }} 人</dd>
          <dt>赛事</dt><dd>{{ resource.data.value.totals.tournaments }} 项 · 通过 {{ resource.data.value.totals.tournament_teams }} 支队伍 · 参赛 {{ resource.data.value.totals.tournament_people }} 人</dd>
          <dt>文章</dt><dd>发布 {{ resource.data.value.totals.articles }} 篇 · 评论 {{ resource.data.value.totals.comments }} 条</dd>
          <dt>战队</dt><dd>新建 {{ resource.data.value.totals.teams }} 支</dd>
        </dl>
      </section>
      <section class="b-form">
        <div class="c-panel__head"><h2 class="b-section__title">逐场</h2><a v-if="resource.data.value.events.length && localHref(resource.data.value.export_url)" :href="localHref(resource.data.value.export_url)" class="c-btn c-btn--secondary c-btn--sm" data-activity-csv><CIcon name="download" />下载 CSV</a></div>
        <table v-if="resource.data.value.events.length" class="c-table c-table--stack" data-activity-events>
          <thead><tr><th>标题</th><th>日期</th><th>类型</th><th>状态</th><th class="is-num">报名人次或队伍</th><th class="is-num">上场或参赛人数</th></tr></thead>
          <tbody><tr v-for="event in resource.data.value.events" :key="event.url" data-activity-event>
            <td><a v-if="localHref(event.url)" class="b-title" :href="localHref(event.url)">{{ event.title }}</a><span v-else>{{ event.title }}</span></td>
            <td data-label="日期">{{ date(event.when).replaceAll('.', '-') }}</td><td data-label="类型">{{ event.kind }}</td><td data-label="状态">{{ event.status }}</td>
            <td data-label="报名人次或队伍" class="is-num">{{ event.entries }}</td><td data-label="上场或参赛人数" class="is-num">{{ event.players }}</td>
          </tr></tbody>
        </table>
        <p v-else class="b-section__text" data-activity-empty>这段时间没有内战和赛事。</p>
      </section>
    </template>
  </AdminPage>
</template>
