<script setup lang="ts">
import { computed, shallowRef } from "vue"
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
import { activityHref, actionHref, notifyHref, statusLabel, timestamp } from "../../pages/activities/domain"
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
  return moved ? `报名的人原来知道的开始时间是 ${timestamp(moved)}。接下来请通知报名的人。` : ""
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
  <form class="b-form" @submit.prevent="save.flush()">
    <AdminNotice v-if="mode === 'copy' && id === null && source" :message="`从「${source.title}」复制：内容和规则照抄，时间按整周挪到将来。改一处就建成一份新的草稿。`" kind="info" />
    <SaveStatus :snapshot="snapshot" :dirty="dirty" :pending="pending" @retry="save.save()" />
    <AdminNotice v-if="notice" :message="notice" kind="warn" />
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
      :team-maximum="detail?.team_max_members ?? props.defaults?.team_max_members ?? null"
      @change="fieldChange"
      @blur="save.flush()"
    />
    <section v-if="id !== null" class="b-section">
      <h2 class="b-section__title">接下来</h2>
      <p class="b-section__text">当前状态：{{ statusLabel(state) }}</p>
      <p v-if="state === 'draft' && missing.length" class="b-section__text">还没填好：{{ missing.join('、') }}。</p>
      <div class="b-actions">
        <RouterLink v-if="state === 'draft'" class="c-btn c-btn--primary" :to="actionHref('tournaments', id, 'publish')">发布赛事</RouterLink>
        <RouterLink v-if="state === 'published'" class="c-btn c-btn--secondary" :to="actionHref('tournaments', id, 'finish')">标记为已结束</RouterLink>
        <RouterLink v-if="state !== 'draft'" class="c-btn c-btn--secondary" :to="notifyHref('tournaments', id, true)">通知报名的人</RouterLink>
        <RouterLink v-if="mode !== 'edit'" class="c-btn c-btn--secondary" :to="activityHref('tournaments', id)">继续编辑</RouterLink>
        <a class="c-btn c-btn--quiet" :href="`/tournaments/${id}/`" target="_blank" rel="noopener">打开网站</a>
      </div>
    </section>
    <div class="b-formbar">
      <span v-if="id === null" class="b-formbar__note">改一处就建成草稿，必填项空着也存；填好以后在「更多」里发布。</span>
      <RouterLink class="c-btn c-btn--secondary" to="/admin/tournaments/">返回</RouterLink>
    </div>
  </form>
</template>
