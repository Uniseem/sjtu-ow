<script setup lang="ts">
import { computed, shallowRef } from "vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import {
  ApiError,
  getApiAdminScrimsId,
  patchApiAdminScrimsId,
  postApiAdminScrims,
  postApiAdminScrimsIdCopy,
} from "@sjtu-ow/api"
import type { GetApiAdminScrimsIdOut } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminSave } from "../../core/use-save"
import { actionHref, notifyHref, statusLabel, timestamp, noticeTime } from "../../pages/activities/domain"
import { blankScrim, currentScrim, scrimValues } from "../../pages/activities/form-schema"
import type { ScrimValues } from "../../pages/activities/form-schema"
import ScrimFields from "./ScrimFields.vue"
import AdminNotice from "../AdminNotice.vue"
import SaveStatus from "../SaveStatus.vue"

const props = defineProps<{
  detail: GetApiAdminScrimsIdOut | null
  defaults?: import("../../pages/activities/pending").ScrimDefaults
  mode: "new" | "edit" | "copy"
}>()
const api = useAdminApi()
const source = props.detail?.scrim ?? null
const id = shallowRef(props.mode === "edit" ? source?.id ?? null : null)
const detail = shallowRef(props.mode === "edit" ? props.detail : null)
const initial = source ? scrimValues(source) : props.defaults?.values ?? blankScrim()
let createdVersion: number | null = null
const copySource = props.mode === "copy" ? source?.id ?? null : null
const save = useAdminSave<ScrimValues>({
  initial,
  version: props.mode === "edit" ? source?.version ?? 0 : 0,
  readCurrent: currentScrim,
  transport: async (body, key, signal) => {
    let version = body.base_version === 0 && createdVersion !== null ? createdVersion : body.base_version
    if (id.value === null) {
      const result = copySource === null
        ? await postApiAdminScrims(api, { key: `${key}:create`, signal, unauthorized: "throw" })
        : await postApiAdminScrimsIdCopy(api, copySource, { key: `${key}:create`, signal, unauthorized: "throw" })
      if (!result.scrim) throw new ApiError(0, "invalid_receipt", "新建回执无效，请重试。")
      id.value = result.scrim.id
      version = result.scrim.version
      createdVersion = version
    }
    const changes = { ...body.changes }
    for (const field of ["starts_at", "signup_closes_at"] as const) {
      if (Object.hasOwn(changes, field) && changes[field] === null) changes[field] = ""
    }
    const result = await patchApiAdminScrimsId(api, id.value, {
      base_version: version,
      changes,
    }, { key: `${key}:patch`, signal, unauthorized: "throw" })
    void getApiAdminScrimsId(api, id.value, { unauthorized: "throw" }).then((value) => {
      detail.value = value
    }).catch(() => undefined)
    return result
  },
})
const { snapshot, values, fields, pending, dirty } = save
const state = computed(() => id.value !== null ? detail.value?.scrim?.status ?? "draft" : "draft")
const missing = computed(() => detail.value?.row?.missing ?? [])
const notice = computed(() => {
  const moved = detail.value?.scrim?.moved_from
  return moved && state.value === "published" ? `开始时间从 ${noticeTime(moved)} 改到了 ${noticeTime(detail.value?.scrim?.starts_at)}，报名的人还不知道。` : ""
})

function fieldChange(name: keyof ScrimValues, value: string | boolean | null, kind: "text" | "choice"): void {
  save.set(name, value as ScrimValues[typeof name], kind)
}
</script>

<template>
  <div :class="id !== null ? 'b-split' : 'b-single'">
  <form class="b-form" @submit.prevent="save.flush()">
    <SaveStatus :snapshot="snapshot" :dirty="dirty" :pending="pending" @retry="save.save()" />
    <div v-if="mode === 'copy' && id === null && source" class="c-notice c-notice--info"><CIcon name="copy" /><div class="c-notice__body">从「{{ source.title }}」复制：内容和规则照抄，时间按整周挪到将来。改一处就建成一份新的草稿。</div></div>
    <AdminNotice
      v-if="id !== null && mode !== 'edit'"
      :message="mode === 'copy' ? '已复制为一项新的草稿，原来的内战不变。' : '草稿已建立。'"
      kind="info"
    />
    <ScrimFields
      :values="values"
      :committed="snapshot.committed"
      :fields="fields"
      :disabled="snapshot.loginRequired"
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
        <dt>报名</dt><dd>{{ detail?.row?.signup_total ?? 0 }} 人</dd>
        <template v-if="detail?.scrim?.teams_generated_at"><dt>分队</dt><dd>{{ timestamp(detail.scrim.teams_generated_at) }}</dd></template>
        <template v-if="detail?.creator_nickname"><dt>建立人</dt><dd>{{ detail.creator_nickname }}</dd></template>
      </dl>
      <a v-if="state !== 'draft'" class="c-btn c-btn--secondary c-btn--sm" :href="`/scrims/${id}/`" target="_blank" rel="noopener">看活动页<CIcon name="external" class="size-4" /></a>
    </section>
    <section class="b-section">
      <h2 class="b-section__title">接下来</h2>
      <div v-if="notice" class="c-notice c-notice--warn" data-time-moved>
        <CIcon name="clock" /><div class="c-notice__body">{{ notice }}<RouterLink :to="notifyHref('scrims', id, true)">通知报名的人</RouterLink></div>
      </div>
      <ul class="b-list">
        <li v-if="state === 'draft'"><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="actionHref('scrims', id, 'publish')">发布</RouterLink></li>
        <li v-if="state === 'published'"><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="notifyHref('scrims', id)">通知全体成员</RouterLink></li>
        <li v-if="state === 'published'"><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="notifyHref('scrims', id, true)">通知报名的人</RouterLink></li>
        <li v-if="state === 'published'"><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="actionHref('scrims', id, 'finish')">标记为已结束</RouterLink></li>
        <li v-if="state !== 'draft'"><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="`/admin/scrims/${id}/split/`">分队</RouterLink></li>
        <li><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="`/admin/scrims/copy/${id}/`">复制</RouterLink></li>
        <li v-if="state !== 'cancelled' && (state !== 'draft' || !missing.length)"><RouterLink class="c-btn c-btn--quiet c-btn--sm is-danger" :to="actionHref('scrims', id, 'cancel')">取消内战</RouterLink></li>
        <li v-if="detail?.row?.can_delete"><RouterLink class="c-btn c-btn--quiet c-btn--sm is-danger" :to="actionHref('scrims', id, 'delete')">删除</RouterLink></li>
      </ul>
    </section>
  </aside>
  </div>
</template>
