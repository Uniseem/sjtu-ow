<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef } from "vue"
import { onBeforeRouteLeave, onBeforeRouteUpdate } from "vue-router"
import { ApiError, getApiAdminTournamentsIdBoard } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import type { TournamentBoard } from "../../pages/activities/domain"
import { timestamp } from "../../pages/activities/domain"
import {
  addZone,
  benchEntries,
  dissolveZone,
  layoutEqual,
  layoutErrors,
  layoutFromBoard,
  layoutPayload,
  placeEntry,
  renameZone,
  zoneEntries,
  zoneProblems,
} from "../../pages/activities/team-board-model"
import type { TeamLayout, TeamZone } from "../../pages/activities/team-board-model"
import { saveTeamBoard } from "../../pages/activities/pending"
import type { SafeTeamBoardRequest } from "../../pages/activities/pending"
import TeamBoardCard from "./TeamBoardCard.vue"
import AdminNotice from "../AdminNotice.vue"
import { useSortableBoard } from "./use-sortable-board"

const props = defineProps<{ initial: TournamentBoard; minimum: number; id: number }>()
const api = useAdminApi()
const board = shallowRef(props.initial)
const committed = shallowRef(layoutFromBoard(props.initial))
const layout = shallowRef(addZone(committed.value, "new-1"))
const warning = shallowRef("")
const success = shallowRef("")
const reloadError = shallowRef("")
const reloading = shallowRef(false)
const dissolve = shallowRef<TeamZone | null>(null)
const root = ref<HTMLElement | null>(null)
let newNumber = 1
const stableLayout = (value: TeamLayout) => ({ ...value, zones: value.zones.filter((zone) => zone.registration_id !== null || zone.signup_ids.length || zone.name) })
const dirty = computed(() => !layoutEqual(stableLayout(layout.value), stableLayout(committed.value)))
const errors = computed(() => layoutErrors(board.value, layout.value))
const bench = computed(() => benchEntries(board.value, layout.value))
const mutation = useAdminAction<SafeTeamBoardRequest, { created: number; updated: number; dissolved: number; returned: number }>(
  async (body, extras) => {
    try {
      return await saveTeamBoard(api, props.id, body, extras)
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        warning.value = "另一个人刚改过名单，未保存本次编排。请刷新名单后再调整。"
      }
      throw error
    }
  },
  async (result) => {
    success.value = `编队已保存：新建 ${result.created} 支，更新 ${result.updated} 支，解散 ${result.dissolved} 支，回池 ${result.returned} 人。`
    // The receipt confirms persistence before the read. Keep this distinction
    // if refreshing fails; never enable resubmission against an old board.
    await refreshAfterSave()
  },
)
const { pending, message, fields, uncertain } = mutation
const disabled = computed(() => pending.value || uncertain.value || reloading.value || Boolean(reloadError.value))
const canSave = computed(() => !disabled.value && dirty.value && !errors.value.length && layout.value.base_pool_version !== null)

function move(id: number, target: string): void {
  if (disabled.value) return
  const result = placeEntry(board.value, layout.value, id, target)
  warning.value = result.message
  if (!result.message) {
    layout.value = result.layout
    success.value = ""
    void nextTick(() => root.value?.querySelector<HTMLElement>(`[data-signup="${id}"]`)?.focus())
  }
}

function rename(key: string, event: Event): void {
  if (disabled.value || !(event.target instanceof HTMLInputElement)) return
  layout.value = renameZone(layout.value, key, event.target.value)
  success.value = ""
}

function add(): void {
  if (disabled.value) return
  newNumber += 1
  layout.value = addZone(layout.value, `new-${newNumber}`)
}

function confirmDissolve(): void {
  if (disabled.value || !dissolve.value) return
  layout.value = dissolveZone(layout.value, dissolve.value.key)
  dissolve.value = null
  success.value = ""
}

async function save(): Promise<void> {
  if (!canSave.value) return
  const payload = layoutPayload(layout.value)
  if (payload) await mutation.submit(payload)
}

async function refreshAfterSave(saved = true): Promise<void> {
  reloading.value = true
  reloadError.value = ""
  try {
    const current = await getApiAdminTournamentsIdBoard(api, props.id, { unauthorized: "throw" })
    if (!current.tournament) throw new ApiError(404, "not_found", "赛事已不存在。")
    board.value = current
    committed.value = layoutFromBoard(current)
    layout.value = addZone(committed.value, `new-${++newNumber}`)
    warning.value = ""
  } catch (error) {
    const prefix = saved ? "编队已保存，但刷新名单失败" : "刷新名单失败，本次调整仍保留"
    reloadError.value = error instanceof Error ? `${prefix}：${error.message}` : `${prefix}，请重试刷新。`
  } finally {
    reloading.value = false
  }
}

async function discardAndReload(): Promise<void> {
  if (pending.value || uncertain.value) return
  // The explicit button below is labelled with its discard consequence.
  await refreshAfterSave(false)
}

function leave(): boolean {
  if (!dirty.value || success.value) return true
  warning.value = "编队还没保存，请先保存编队，或放弃本次调整。"
  return false
}

function beforeUnload(event: BeforeUnloadEvent): void {
  if (!dirty.value && !uncertain.value) return
  event.preventDefault()
  event.returnValue = ""
}

onBeforeRouteLeave(leave)
onBeforeRouteUpdate(leave)
onMounted(() => window.addEventListener("beforeunload", beforeUnload))
onUnmounted(() => window.removeEventListener("beforeunload", beforeUnload))
useSortableBoard(root, () => layout.value, () => !disabled.value, move, (value) => { warning.value = value })
</script>

<template>
  <section class="b-section">
    <dl class="b-kv">
      <dt>每队人数</dt><dd>{{ minimum }}–{{ board.roster_max }} 人</dd>
      <dt>个人报名</dt><dd>{{ board.entries.length }} 人，其中散人池 {{ bench.length }} 人</dd>
      <dt>报名截止</dt><dd>{{ timestamp(board.tournament?.registration_closes_at) }}</dd>
    </dl>
  </section>
  <AdminNotice v-if="board.tournament?.registration_mode !== 'individual'" message="这项赛事是整队报名，不收个人报名。已有的临时队伍仍可以在这里调整。" kind="warn" />
  <AdminNotice v-if="layout.base_pool_version === null" message="名单暂时无法保存，请刷新名单后再试。" kind="warn" />
  <AdminNotice message="把散人拖进队伍，或者用卡片上的按钮移动。队伍满员时不能直接拖进去，先把要换下来的人拖回散人池。人数低于下限的队伍标红，但仍然可以保存。保存后问你要不要给新编入的人发信。" kind="info" />
  <AdminNotice v-if="success" :message="success" kind="ok" />
  <AdminNotice v-if="warning" :message="warning" kind="warn" />
  <AdminNotice v-if="message" :message="message" kind="error" />
  <AdminNotice v-if="reloadError" :message="reloadError" kind="error" />
  <ul v-if="errors.length" class="c-field__error" role="alert"><li v-for="error in errors" :key="error">{{ error }}</li></ul>
  <ul v-for="(items, field) in fields" :key="field" class="c-field__error" role="alert"><li v-for="error in items" :key="error">{{ error }}</li></ul>
  <form ref="root" class="b-form" @submit.prevent="save">
    <div class="split-teams">
      <div v-for="zone in layout.zones" :key="zone.key" class="split-team" :data-team-panel="zone.key">
        <h3 class="b-section__title">
          <label :for="`name-${zone.key}`">{{ zone.registration_id ? '队名' : '新队伍' }}</label>
          <input
            :id="`name-${zone.key}`"
            class="c-input split-name"
            type="text"
            maxlength="16"
            :value="zone.name"
            :disabled="disabled"
            :placeholder="zone.registration_id ? '' : '拖人进来后填队名'"
            @input="rename(zone.key, $event)"
          >
        </h3>
        <p v-if="zoneProblems(zone, minimum, board.roster_max).length" class="split-problem">{{ zoneProblems(zone, minimum, board.roster_max).join('、') }}</p>
        <section class="split-zone">
          <h4 class="split-zone-title">名单（{{ zone.signup_ids.length }}/{{ board.roster_max }}）</h4>
          <ul class="split-list" :data-board-zone="zone.key" :aria-label="`${zone.name || '新队伍'}名单`">
            <TeamBoardCard
              v-for="entry in zoneEntries(board, zone)"
              :key="entry.signup_id"
              :entry="entry"
              :targets="layout.zones"
              :current="zone.key"
              :disabled="disabled"
              @move="move"
            />
          </ul>
        </section>
        <button v-if="zone.registration_id !== null || zone.signup_ids.length || zone.name" type="button" class="c-btn c-btn--danger c-btn--sm" :disabled="disabled" @click="dissolve = zone">解散</button>
        <RouterLink v-if="zone.registration_id" class="c-btn c-btn--quiet c-btn--sm" :to="`/admin/registrations/${zone.registration_id}/`">报名详情</RouterLink>
      </div>
    </div>
    <button type="button" class="c-btn c-btn--secondary" :disabled="disabled" @click="add">再加一支队伍</button>
    <div class="split-buffer">
      <section class="split-zone">
        <h4 class="split-zone-title">散人池（等待编队）（{{ bench.length }}）</h4>
        <ul class="split-list" data-board-zone="" aria-label="散人池（等待编队）">
          <TeamBoardCard v-for="entry in bench" :key="entry.signup_id" :entry="entry" :targets="layout.zones" current="" :disabled="disabled" @move="move" />
        </ul>
      </section>
      <p class="b-sub">留在这里的人还没有队伍。标着「已在战队名单中」的人不能编入。</p>
    </div>
    <section v-if="dissolve" class="b-section" role="alertdialog" aria-labelledby="dissolve-heading" aria-describedby="dissolve-help">
      <h2 id="dissolve-heading" class="b-section__title">解散队伍：{{ dissolve.name || '新队伍' }}</h2>
      <p id="dissolve-help" class="b-section__text">解散这支临时队伍？成员回到散人池。保存编队后才生效，再问你要不要发信告诉他们。</p>
      <div class="b-actions">
        <button type="button" class="c-btn c-btn--danger" :disabled="disabled" @click="confirmDissolve">确认解散</button>
        <button type="button" class="c-btn c-btn--secondary" @click="dissolve = null">返回</button>
      </div>
    </section>
    <div class="b-formbar">
      <button type="submit" class="c-btn c-btn--primary" :disabled="!canSave">{{ pending ? '正在保存…' : '保存编队' }}</button>
      <button v-if="uncertain" type="button" class="c-btn c-btn--secondary" :disabled="pending" @click="mutation.retry()">重试上次保存</button>
      <button v-if="reloadError" type="button" class="c-btn c-btn--secondary" :disabled="reloading" @click="() => refreshAfterSave()">重试刷新名单</button>
      <button v-if="dirty && !uncertain && !pending && !reloadError" type="button" class="c-btn c-btn--quiet" @click="discardAndReload">放弃本次调整并刷新名单</button>
      <span class="b-formbar__note">{{ dirty ? '编队还没保存。' : '当前没有待保存的调整。' }}</span>
    </div>
  </form>
</template>
