<script setup lang="ts">
import { showReadError } from "../../core/read-error"
import { computed, onMounted, onUnmounted, shallowRef, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiAdminScrims, getApiAdminTournaments } from "@sjtu-ow/api"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import { useAdminApi } from "../../core/api"
import AdminPage from "../../components/AdminPage.vue"
import AdminNotice from "../../components/AdminNotice.vue"
import ActivityPager from "../../components/activities/ActivityPager.vue"
import {
  actionHref,
  activityHref,
  activityLabel,
  formatLabel,
  modeLabel,
  modeOptions,
  notifyHref,
  queryText,
  record,
  statusLabel,
  statusOptions,
  timestamp,
} from "./domain"
import type { ActivityKind, ScrimRow, TournamentRow } from "./domain"

const props = defineProps<{ kind: ActivityKind }>()
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const tournaments = shallowRef<TournamentRow[]>([])
const scrims = shallowRef<ScrimRow[]>([])
const pending = shallowRef(true)
const message = shallowRef("")
const search = shallowRef(queryText(route.query.q))
const status = shallowRef(queryText(route.query.status))
const mode = shallowRef(queryText(route.query.mode))
let sequence = 0
let request: AbortController | null = null
// Form edits take effect after submitting, as on the legacy GET form.
const appliedSearch = computed(() => Array.from(queryText(route.query.q).trim()).slice(0, 50).join("").toLocaleLowerCase())
const appliedStatus = computed(() => statusOptions.some((option) => option.value === route.query.status) ? queryText(route.query.status) : "")
const appliedMode = computed(() => modeOptions.some((option) => option.value === route.query.mode) ? queryText(route.query.mode) : "")
const filteredTournaments = computed(() => tournaments.value.filter((item) => {
  return (!appliedSearch.value || `${item.title} ${item.summary}`.toLocaleLowerCase().includes(appliedSearch.value))
    && (!appliedStatus.value || item.status === appliedStatus.value)
    && (!appliedMode.value || item.registration_mode === appliedMode.value)
}))
const filteredScrims = computed(() => scrims.value.filter((item) => {
  return (!appliedSearch.value || `${item.title} ${record(item)?.description_plain ?? record(item)?.description ?? ""}`.toLocaleLowerCase().includes(appliedSearch.value))
    && (!appliedStatus.value || item.status === appliedStatus.value)
}))
const perPage = 30
const pageNumber = computed(() => {
  const requested = Number(route.query.page)
  return Number.isSafeInteger(requested) && requested > 0 ? requested : 1
})
const count = computed(() => props.kind === "tournaments" ? filteredTournaments.value.length : filteredScrims.value.length)

const pageCount = computed(() => Math.max(1, Math.ceil(count.value / perPage)))
const currentPage = computed(() => Math.min(pageNumber.value, pageCount.value))
const visibleTournaments = computed(() => filteredTournaments.value.slice((currentPage.value - 1) * perPage, currentPage.value * perPage))
const visibleScrims = computed(() => filteredScrims.value.slice((currentPage.value - 1) * perPage, currentPage.value * perPage))
function pageHref(page: number) {
  return { path: activityHref(props.kind), query: { ...route.query, page: String(page) } }
}

function compareActivityTime(a: string | null | undefined, b: string | null | undefined): number {
  if (!a) return b ? -1 : 0
  if (!b) return 1
  return Date.parse(b) - Date.parse(a)
}

async function load(): Promise<void> {
  request?.abort()
  request = new AbortController()
  const token = ++sequence
  pending.value = true
  message.value = ""
  try {
    if (props.kind === "tournaments") {
      const result = await getApiAdminTournaments(api, { signal: request.signal })
      if (sequence !== token) return
      tournaments.value = [...result.tournaments].sort((a, b) => compareActivityTime(a.registration_opens_at, b.registration_opens_at) || b.id - a.id)
    } else {
      const result = await getApiAdminScrims(api, { signal: request.signal })
      if (sequence !== token) return
      scrims.value = [...result.scrims].sort((a, b) => compareActivityTime(a.starts_at, b.starts_at) || b.id - a.id)
    }
  } catch (error) {
    if (sequence !== token || request.signal.aborted) return
    showReadError(error)
    message.value = error instanceof Error ? error.message : "暂时无法加载，请稍后再试。"
  } finally {
    if (sequence === token) pending.value = false
  }
}

async function filter(): Promise<void> {
  const query: Record<string, string> = {}
  if (search.value.trim()) query.q = Array.from(search.value.trim()).slice(0, 50).join("")
  if (status.value) query.status = status.value
  if (props.kind === "tournaments" && mode.value) query.mode = mode.value
  await router.replace({ path: activityHref(props.kind), query })
}

function noticeSuffix(item: unknown, field: string): string {
  const count = Number(record(item)?.[field])
  return Number.isSafeInteger(count) && count > 0 ? `（发过 ${count} 次）` : ""
}

watch(() => route.query, (query) => {
  search.value = queryText(query.q)
  status.value = queryText(query.status)
  mode.value = queryText(query.mode)
})
watch(() => props.kind, load)
onMounted(load)
onUnmounted(() => { sequence += 1; request?.abort() })
</script>

<template>
  <AdminPage :title="activityLabel(kind)" section="events">
    <template #actions>
      <RouterLink class="c-btn c-btn--primary c-btn--sm" :to="`${activityHref(kind)}new/`"><CIcon name="plus" />新建{{ activityLabel(kind) }}</RouterLink>
    </template>
    <form class="b-filters" role="search" @submit.prevent="filter">
      <input v-model="search" class="c-input" type="search" name="q" :maxlength="50" :placeholder="kind === 'tournaments' ? '搜标题、简介' : '搜标题、说明'" :aria-label="kind === 'tournaments' ? '搜赛事' : '搜内战'">
      <select v-model="status" class="c-input" name="status" aria-label="状态" @change="filter">
        <option v-for="option in statusOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
      <select v-if="kind === 'tournaments'" v-model="mode" class="c-input" name="mode" aria-label="报名方式" @change="filter">
        <option value="">全部报名方式</option>
        <option v-for="option in modeOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
      <button class="c-btn c-btn--secondary c-btn--sm" type="submit">筛选</button>
    </form>
    <p v-if="pending" role="status">正在加载…</p>
    <AdminNotice v-else-if="message" :message="message" kind="error" />
    <template v-else>
      <table v-if="kind === 'tournaments' && filteredTournaments.length" class="c-table c-table--stack">
        <thead>
          <tr>
            <th scope="col">{{ activityLabel(kind) }}</th>
            <th scope="col">状态</th>
            <th scope="col">报名开始</th>
            <th scope="col">报名截止</th>
            <th scope="col">待审核</th>
            <th scope="col"><span class="sr-only">操作</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in visibleTournaments" :key="item.id" :data-tournament-row="item.id">
            <td>
              <RouterLink class="b-title" :to="activityHref('tournaments', item.id)">{{ item.title || '（未命名赛事）' }}</RouterLink>
              <span class="b-sub">{{ modeLabel(item.registration_mode) }}</span>
            </td>
            <td data-label="状态">{{ statusLabel(item.status) }}</td>
            <td data-label="报名开始">{{ item.registration_opens_at ? timestamp(item.registration_opens_at) : '' }}</td>
            <td data-label="报名截止">{{ item.registration_closes_at ? timestamp(item.registration_closes_at) : '' }}</td>
            <td data-label="待审核">
              <RouterLink v-if="item.pending_count" class="c-link" data-pending :to="`/admin/registrations/?tournament=${item.id}&status=pending`">{{ item.pending_count }} 份</RouterLink>
              <span v-else>—</span>
            </td>
            <td>
              <div class="b-rowacts">
                <RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="activityHref('tournaments', item.id)">编辑</RouterLink>
                <details class="b-more c-menu">
                  <summary aria-label="更多操作">更多<CIcon name="chevron-down" class="size-4" /></summary>
                  <div class="c-menu__panel">
                    <RouterLink v-if="item.status === 'draft'" :to="actionHref('tournaments', item.id, 'publish')">发布</RouterLink>
                    <RouterLink v-if="item.status === 'published'" :to="notifyHref('tournaments', item.id)">通知全体成员{{ noticeSuffix(item, 'everyone_notices') }}</RouterLink>
                    <RouterLink v-if="item.status === 'published'" :to="notifyHref('tournaments', item.id, true)">通知报名的人{{ noticeSuffix(item, 'participant_notices') }}</RouterLink>
                    <RouterLink v-if="item.status === 'published'" :to="actionHref('tournaments', item.id, 'finish')">标记为已结束</RouterLink>
                    <RouterLink :to="`/admin/registrations/?tournament=${item.id}&status=pending`">审核报名</RouterLink>
                    <RouterLink v-if="item.registration_mode === 'individual'" :to="`/admin/tournaments/${item.id}/teams/`">队伍编排</RouterLink>
                    <RouterLink :to="`/admin/tournaments/copy/${item.id}/`">复制</RouterLink>
                    <RouterLink v-if="item.status !== 'cancelled' && (item.status !== 'draft' || !item.missing.length)" class="is-danger" :to="actionHref('tournaments', item.id, 'cancel')">取消赛事</RouterLink>
                    <RouterLink v-if="record(item)?.can_delete === true" class="is-danger" :to="actionHref('tournaments', item.id, 'delete')">删除</RouterLink>
                  </div>
                </details>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <table v-else-if="kind === 'scrims' && filteredScrims.length" class="c-table c-table--stack">
        <thead>
          <tr>
            <th scope="col">{{ activityLabel(kind) }}</th>
            <th scope="col">状态</th>
            <th scope="col">规格</th>
            <th scope="col">开始</th>
            <th scope="col">报名截止</th>
            <th scope="col" class="is-num">报名</th>
            <th scope="col"><span class="sr-only">操作</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in visibleScrims" :key="item.id" :data-scrim-row="item.id">
            <td><RouterLink class="b-title" :to="activityHref('scrims', item.id)">{{ item.title || '（未命名内战）' }}</RouterLink></td>
            <td data-label="状态">{{ statusLabel(item.status) }}</td>
            <td data-label="规格">{{ item.format_label || formatLabel(item.format) }}</td>
            <td data-label="开始">{{ item.starts_at ? timestamp(item.starts_at) : '' }}</td>
            <td data-label="报名截止">{{ item.signup_deadline ? timestamp(item.signup_deadline) : '' }}</td>
            <td data-label="报名" class="is-num">{{ item.signup_total }}</td>
            <td>
              <div class="b-rowacts">
                <RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="activityHref('scrims', item.id)">编辑</RouterLink>
                <details class="b-more c-menu">
                  <summary aria-label="更多操作">更多<CIcon name="chevron-down" class="size-4" /></summary>
                  <div class="c-menu__panel">
                    <RouterLink v-if="item.status === 'draft'" :to="actionHref('scrims', item.id, 'publish')">发布</RouterLink>
                    <RouterLink v-if="item.status === 'published'" :to="notifyHref('scrims', item.id)">通知全体成员{{ noticeSuffix(item, 'everyone_notices') }}</RouterLink>
                    <RouterLink v-if="item.status === 'published'" :to="notifyHref('scrims', item.id, true)">通知报名的人{{ noticeSuffix(item, 'participant_notices') }}</RouterLink>
                    <RouterLink v-if="item.status === 'published'" :to="actionHref('scrims', item.id, 'finish')">标记为已结束</RouterLink>
                    <RouterLink v-if="item.status !== 'draft'" :to="`/admin/scrims/${item.id}/split/`">分队</RouterLink>
                    <RouterLink :to="`/admin/scrims/copy/${item.id}/`">复制</RouterLink>
                    <RouterLink v-if="item.status !== 'cancelled' && (item.status !== 'draft' || !item.missing.length)" class="is-danger" :to="actionHref('scrims', item.id, 'cancel')">取消内战</RouterLink>
                    <RouterLink v-if="item.can_delete" class="is-danger" :to="actionHref('scrims', item.id, 'delete')">删除</RouterLink>
                  </div>
                </details>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <CEmpty
        v-if="!count"
        :title="kind === 'tournaments' ? '没有赛事' : '没有内战'"
        :message="kind === 'tournaments' ? '换个筛选条件，或者新建一项。' : '换个筛选条件，或者新建一场。'"
        :action-url="`${activityHref(kind)}new/`"
        :action-label="kind === 'tournaments' ? '新建赛事' : '新建内战'"
      />
      <ActivityPager :page="currentPage" :pages="pageCount" :previous="pageHref(currentPage - 1)" :next="pageHref(currentPage + 1)" />
    </template>
    <button v-if="message" type="button" class="c-btn c-btn--secondary" @click="load">重试</button>
  </AdminPage>
</template>
