<script setup lang="ts">
import { computed, shallowRef } from "vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import {
  ApiError,
  getApiAdminTournamentsId,
  patchApiAdminTournamentsId,
  postApiAdminTournaments,
  postApiAdminTournamentsIdCopy,
} from "@sjtu-ow/api"
import type { GetApiAdminTournamentsIdOut } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminSave } from "../../core/use-save"
import { actionHref, notifyHref, statusLabel, timestamp, noticeTime } from "../../pages/activities/domain"
import { blankTournament, currentTournament, tournamentValues } from "../../pages/activities/form-schema"
import type { TournamentValues } from "../../pages/activities/form-schema"
import TournamentFields from "./TournamentFields.vue"
import AdminNotice from "../AdminNotice.vue"
import SaveStatus from "../SaveStatus.vue"

const props = defineProps<{
  detail: GetApiAdminTournamentsIdOut | null
  defaults?: import("../../pages/activities/pending").TournamentDefaults
  mode: "new" | "edit" | "copy"
}>()
const api = useAdminApi()
const source = props.detail?.tournament ?? null
const id = shallowRef(props.mode === "edit" ? source?.id ?? null : null)
const detail = shallowRef(props.mode === "edit" ? props.detail : null)
const initial = source ? tournamentValues(source) : props.defaults?.values ?? blankTournament()
const sourceVersion = props.mode === "edit" ? source?.version ?? 0 : 0
let createdVersion: number | null = null
const copySource = props.mode === "copy" ? source?.id ?? null : null
const save = useAdminSave<TournamentValues>({
  initial,
  version: sourceVersion,
  readCurrent: currentTournament,
  transport: async (body, key, signal) => {
    let version = body.base_version === 0 && createdVersion !== null ? createdVersion : body.base_version
    if (id.value === null) {
      const result = copySource === null
        ? await postApiAdminTournaments(api, { key: `${key}:create`, signal, unauthorized: "throw" })
        : await postApiAdminTournamentsIdCopy(api, copySource, { key: `${key}:create`, signal, unauthorized: "throw" })
      if (!result.tournament) throw new ApiError(0, "invalid_receipt", "新建回执无效，请重试。")
      id.value = result.tournament.id
      version = result.tournament.version
      createdVersion = version
    }
    const changes = { ...body.changes }
    for (const field of ["starts_at", "registration_opens_at", "registration_closes_at"] as const) {
      if (Object.hasOwn(changes, field) && changes[field] === null) changes[field] = ""
    }
    // null cover carries a separate explicit remove bit in the legacy Go patch.
    const result = await patchApiAdminTournamentsId(api, id.value, {
      base_version: version,
      changes: {
        ...changes,
        ...(Object.hasOwn(changes, "cover_image_id") && changes.cover_image_id === null ? { remove_cover: true } : {}),
      },
    }, { key: `${key}:patch`, signal, unauthorized: "throw" })
    // Read metadata only after a successful write. An auxiliary read failure
    // must not turn the write into an uncertain/replayed creation.
    void getApiAdminTournamentsId(api, id.value, { unauthorized: "throw" }).then((value) => {
      detail.value = value
    }).catch(() => undefined)
    return { ...result, saved: [...new Set(result.saved.map((field) => field === "remove_cover" ? "cover_image_id" : field))] }
  },
})
const { snapshot, values, fields, pending, dirty } = save
const savedObject = computed(() => props.mode === "edit" || id.value !== null)
const lockedMode = computed(() => savedObject.value && Boolean(detail.value?.has_entries))
const lockedApproval = computed(() => savedObject.value && Boolean(detail.value?.has_registrations))
const state = computed(() => savedObject.value ? detail.value?.tournament?.status ?? "draft" : "draft")
const missing = computed(() => detail.value?.missing ?? [])
const notice = computed(() => {
  const moved = detail.value?.tournament?.moved_from
  return moved && state.value === "published" ? `开始时间从 ${noticeTime(moved)} 改到了 ${noticeTime(detail.value?.tournament?.starts_at)}，报名的人还不知道。` : ""
})

function change<K extends keyof TournamentValues>(name: K, value: TournamentValues[K], kind: "text" | "choice"): void {
  save.set(name, value, kind)
}

function fieldChange(name: keyof TournamentValues, value: string | number | boolean | null, kind: "text" | "choice"): void {
  // The field component only emits the declared field's concrete value.
  change(name, value as TournamentValues[typeof name], kind)
}
</script>

<template>
  <div :class="id !== null ? 'b-split' : 'b-single'">
  <form class="b-form" @submit.prevent="save.flush()">
    <SaveStatus :snapshot="snapshot" :dirty="dirty" :pending="pending" @retry="save.save()" />
    <div v-if="mode === 'copy' && id === null && source" class="c-notice c-notice--info"><CIcon name="copy" /><div class="c-notice__body">从「{{ source.title }}」复制：内容和规则照抄，时间按整周挪到将来。改一处就建成一份新的草稿。</div></div>
    <AdminNotice
      v-if="id !== null && mode !== 'edit'"
      :message="mode === 'copy' ? '已复制为一项新的草稿，原来的赛事不变。' : '草稿已建立。'"
      kind="info"
    />
    <TournamentFields
      :values="values"
      :committed="snapshot.committed"
      :fields="fields"
      :disabled="snapshot.loginRequired"
      :has-entries="lockedMode"
      :has-registrations="lockedApproval"
      :team-maximum="detail?.team_max_members ?? props.detail?.team_max_members ?? props.defaults?.team_max_members ?? null"
      @change="fieldChange"
      @blur="save.flush()"
    />
    <div v-if="id === null" class="b-formbar">
      <span v-if="id === null" class="b-formbar__note">改一处就建成草稿，必填项空着也存；填好以后在「更多」里发布。</span>
    </div>
  </form>
  <aside v-if="id !== null" class="b-aside">
    <section class="b-section">
      <h2 class="b-section__title">状态</h2>
      <dl class="b-kv">
        <dt>状态</dt><dd>{{ statusLabel(state) }}</dd>
        <template v-if="detail?.tournament?.published_at"><dt>首次发布</dt><dd>{{ timestamp(detail.tournament.published_at) }}</dd></template>
        <dt>报名</dt><dd>{{ detail?.registration_count ?? 0 }} 份</dd>
        <template v-if="detail?.creator_nickname"><dt>建立人</dt><dd>{{ detail.creator_nickname }}</dd></template>
      </dl>
      <a v-if="state !== 'draft'" class="c-btn c-btn--secondary c-btn--sm" :href="`/tournaments/${id}/`" target="_blank" rel="noopener">看活动页<CIcon name="external" class="size-4" /></a>
    </section>
    <section class="b-section">
      <h2 class="b-section__title">接下来</h2>
      <div v-if="notice" class="c-notice c-notice--warn" data-time-moved>
        <CIcon name="clock" /><div class="c-notice__body">{{ notice }}<RouterLink :to="notifyHref('tournaments', id, true)">通知报名的人</RouterLink></div>
      </div>
      <ul class="b-list">
        <li v-if="state === 'draft'"><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="actionHref('tournaments', id, 'publish')">发布</RouterLink></li>
        <li v-if="state === 'published'"><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="notifyHref('tournaments', id)">通知全体成员</RouterLink></li>
        <li v-if="state === 'published'"><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="notifyHref('tournaments', id, true)">通知报名的人</RouterLink></li>
        <li v-if="state === 'published'"><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="actionHref('tournaments', id, 'finish')">标记为已结束</RouterLink></li>
        <li><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="`/admin/registrations/?tournament=${id}&status=pending`">审核报名</RouterLink></li><li v-if="values.registration_mode === 'individual'"><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="`/admin/tournaments/${id}/teams/`">队伍编排</RouterLink></li>
        <li><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="`/admin/tournaments/copy/${id}/`">复制</RouterLink></li>
        <li v-if="state !== 'cancelled' && (state !== 'draft' || !missing.length)"><RouterLink class="c-btn c-btn--quiet c-btn--sm is-danger" :to="actionHref('tournaments', id, 'cancel')">取消赛事</RouterLink></li>
        <li v-if="detail?.can_delete"><RouterLink class="c-btn c-btn--quiet c-btn--sm is-danger" :to="actionHref('tournaments', id, 'delete')">删除</RouterLink></li>
      </ul>
    </section>
  </aside>
  </div>
</template>
