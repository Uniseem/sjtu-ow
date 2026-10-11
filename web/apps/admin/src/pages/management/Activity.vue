<script setup lang="ts">
import { ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiAdminActivity } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import { text, date, state, localHref } from "./format"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const preset = ref(text(route.query.preset))
const start = ref(text(route.query.start))
const end = ref(text(route.query.end))
const resource = useResource(() => route.fullPath, signal => getApiAdminActivity(api, { preset: text(route.query.preset), start: text(route.query.start), end: text(route.query.end) }, { signal }))
const labels: Record<string, string> = { members: '新加入的成员', sjtu_members: '交大成员', scrims: '内战', scrim_signups: '内战报名', scrim_players: '内战上场人次', scrim_people: '内战参加人数', tournaments: '赛事', tournament_teams: '赛事报名队伍', tournament_people: '赛事参加人数', articles: '文章', comments: '评论', teams: '新建战队' }
function filter() { void router.push({ path: route.path, query: { preset: preset.value || undefined, start: start.value || undefined, end: end.value || undefined } }) }
</script>
<template>
  <AdminPage title="活动数据" section="数据">
    <form class="b-filters" @submit.prevent="filter">
      <select v-model="preset" class="c-input" aria-label="时间范围">
        <option value="">自选日期</option>
        <option v-for="value in resource.data.value?.presets" :key="value" :value="value">{{ value }}</option>
      </select>
      <label>开始<input v-model="start" class="c-input" type="date" />
    </label>
    <label>结束<input v-model="end" class="c-input" type="date" />
  </label>
  <button class="c-btn c-btn--secondary c-btn--sm">查看</button>
  </form>
  <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
  <template v-if="resource.data.value">
    <p class="b-section__text">{{ date(resource.data.value.period.start) }} — {{ date(resource.data.value.period.end) }}</p>
    <p v-if="resource.data.value.notice" class="b-sub">{{ resource.data.value.notice }}</p>
    <section class="b-section">
      <h2 class="b-section__title">汇总</h2>
      <dl class="b-kv">
        <template v-for="(value, key) in resource.data.value.totals" :key="key">
          <dt>{{ labels[key] || key }}</dt>
          <dd>{{ value }}</dd>
        </template>
      </dl>
    </section>
    <section class="b-section">
      <h2 class="b-section__title">活动</h2>
      <table v-if="resource.data.value.events.length" class="c-table">
        <thead>
          <tr>
            <th scope="col">时间</th>
            <th scope="col">活动</th>
            <th scope="col">状态</th>
            <th scope="col">报名</th>
            <th scope="col">人数</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="event in resource.data.value.events" :key="event.url">
            <td>{{ date(event.when) }}</td>
            <td>
              <a v-if="localHref(event.url)" class="b-title" :href="localHref(event.url)">{{ event.title }}</a>
              <span v-else>{{ event.title }}</span>
              <span class="b-sub">{{ event.kind === 'scrim' ? '内战' : '赛事' }}</span>
            </td>
            <td>{{ state(event.status) }}</td>
            <td>{{ event.entries }}</td>
            <td>{{ event.players }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="b-sub">这个时间段没有活动。</p>
    </section>
  </template>
  </AdminPage>
</template>
