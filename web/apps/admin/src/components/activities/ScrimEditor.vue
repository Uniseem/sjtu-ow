<script setup lang="ts">
import { computed, shallowRef } from "vue"
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
import { activityHref, actionHref, notifyHref, statusLabel, timestamp } from "../../pages/activities/domain"
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
  return moved ? `报名的人原来知道的开始时间是 ${timestamp(moved)}。接下来请通知报名的人。` : ""
})

function fieldChange(name: keyof ScrimValues, value: string | boolean | null, kind: "text" | "choice"): void {
  save.set(name, value as ScrimValues[typeof name], kind)
}
</script>

<template>
  <form class="b-form" @submit.prevent="save.flush()">
    <AdminNotice v-if="mode === 'copy' && id === null && source" :message="`从「${source.title}」复制：内容和规则照抄，时间按整周挪到将来。改一处就建成一份新的草稿。`" kind="info" />
    <SaveStatus :snapshot="snapshot" :dirty="dirty" :pending="pending" @retry="save.save()" />
    <AdminNotice v-if="notice" :message="notice" kind="warn" />
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
    <section v-if="id !== null" class="b-section">
      <h2 class="b-section__title">接下来</h2>
      <p class="b-section__text">当前状态：{{ statusLabel(state) }}</p>
      <p v-if="state === 'draft' && missing.length" class="b-section__text">还没填好：{{ missing.join('、') }}。</p>
      <div class="b-actions">
        <RouterLink v-if="state === 'draft'" class="c-btn c-btn--primary" :to="actionHref('scrims', id, 'publish')">发布内战</RouterLink>
        <RouterLink v-if="state === 'published'" class="c-btn c-btn--secondary" :to="actionHref('scrims', id, 'finish')">标记为已结束</RouterLink>
        <RouterLink v-if="state !== 'draft'" class="c-btn c-btn--secondary" :to="notifyHref('scrims', id, true)">通知报名的人</RouterLink>
        <RouterLink v-if="mode !== 'edit'" class="c-btn c-btn--secondary" :to="activityHref('scrims', id)">继续编辑</RouterLink>
        <a class="c-btn c-btn--quiet" :href="`/scrims/${id}/`" target="_blank" rel="noopener">打开网站</a>
      </div>
    </section>
    <div class="b-formbar">
      <span v-if="id === null" class="b-formbar__note">改一处就建成草稿，必填项空着也存；填好以后在「更多」里发布。</span>
      <RouterLink class="c-btn c-btn--secondary" to="/admin/scrims/">返回</RouterLink>
    </div>
  </form>
</template>
