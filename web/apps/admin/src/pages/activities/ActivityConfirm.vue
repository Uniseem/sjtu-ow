<script setup lang="ts">
import { showReadError } from "../../core/read-error"
import { computed, onMounted, shallowRef } from "vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import { useRoute, useRouter } from "vue-router"
import {
  ApiError,
  deleteApiAdminScrimsId,
  deleteApiAdminTournamentsId,
  getApiAdminScrimsId,
  getApiAdminTournamentsId,
  postApiAdminScrimsIdCancel,
  postApiAdminScrimsIdFinish,
  postApiAdminScrimsIdPublish,
  postApiAdminTournamentsIdCancel,
  postApiAdminTournamentsIdFinish,
  postApiAdminTournamentsIdPublish,
} from "@sjtu-ow/api"
import type { GetApiAdminScrimsIdOut, GetApiAdminTournamentsIdOut } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import AdminPage from "../../components/AdminPage.vue"
import AdminNotice from "../../components/AdminNotice.vue"
import ActivityField from "../../components/activities/ActivityField.vue"
import { actionLabel, activityHref, activityLabel, numericId, statusLabel, timestamp } from "./domain"
import type { ActivityAction, ActivityKind } from "./domain"
import { getPublishNoticePreview, noticePreview, publishWithNotice } from "./pending"
import type { ActivityNoticePreview } from "./pending"

const props = defineProps<{ kind: ActivityKind; action: ActivityAction }>()
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const id = numericId(route.params.id)
const tournament = shallowRef<GetApiAdminTournamentsIdOut | null>(null)
const scrim = shallowRef<GetApiAdminScrimsIdOut | null>(null)
const loading = shallowRef(true)
const loadError = shallowRef("")
const reason = shallowRef("")
const announce = shallowRef(false)
const publishPreview = shallowRef<ActivityNoticePreview | null>(null)
const publishPreviewError = shallowRef("")
const name = computed(() => props.kind === "tournaments" ? tournament.value?.tournament?.title : scrim.value?.scrim?.title)
const status = computed(() => props.kind === "tournaments" ? tournament.value?.tournament?.status : scrim.value?.scrim?.status)
const missing = computed(() => props.kind === "tournaments" ? tournament.value?.missing ?? [] : scrim.value?.row?.missing ?? [])
const canDelete = computed(() => props.kind === "tournaments" ? tournament.value?.can_delete === true : scrim.value?.row?.can_delete === true)
const unavailable = computed(() => {
  if (props.action === "delete") return !canDelete.value
  if (props.action === "publish") return status.value !== "draft" || missing.value.length > 0
  if (props.action === "finish") return status.value !== "published"
  return status.value === "cancelled" || (status.value === "draft" && missing.value.length > 0)
})
const mutation = useAdminAction<{ reason: string; announce: boolean; preview_version: string }, unknown>(async (body, extras) => {
  if (unavailable.value) throw new ApiError(409, "state_changed", "当前状态不能执行这个操作，请重新打开页面。")
  if (props.action === "publish" && body.announce) {
    return publishWithNotice(api, props.kind, id, { announce: true, preview_version: body.preview_version }, extras)
  }
  if (props.kind === "tournaments") {
    if (props.action === "publish") return postApiAdminTournamentsIdPublish(api, id, extras)
    if (props.action === "finish") return postApiAdminTournamentsIdFinish(api, id, extras)
    if (props.action === "cancel") return postApiAdminTournamentsIdCancel(api, id, { reason: body.reason }, extras)
    return deleteApiAdminTournamentsId(api, id, extras)
  }
  if (props.action === "publish") return postApiAdminScrimsIdPublish(api, id, extras)
  if (props.action === "finish") return postApiAdminScrimsIdFinish(api, id, extras)
  if (props.action === "cancel") return postApiAdminScrimsIdCancel(api, id, extras)
  return deleteApiAdminScrimsId(api, id, extras)
}, async () => {
  await router.push(activityHref(props.kind))
})
const { pending, message, fields, uncertain } = mutation

async function load(): Promise<void> {
  loading.value = true
  loadError.value = ""
  publishPreviewError.value = ""
  publishPreview.value = null
  announce.value = false
  try {
    if (!id) throw new ApiError(404, "not_found", "找不到这个页面")
    if (props.kind === "tournaments") {
      tournament.value = await getApiAdminTournamentsId(api, id)
      if (!tournament.value.tournament) throw new ApiError(404, "not_found", "找不到这个页面")
    } else {
      scrim.value = await getApiAdminScrimsId(api, id)
      if (!scrim.value.scrim) throw new ApiError(404, "not_found", "找不到这个页面")
    }
    if (props.action === "delete" && !canDelete.value) {
      await router.replace(activityHref(props.kind, id))
      return
    }
  } catch (error) {
    showReadError(error)
    loadError.value = error instanceof Error ? error.message : "暂时无法打开，请稍后再试。"
  } finally {
    loading.value = false
  }
  if (props.action === "publish" && !loadError.value && !unavailable.value) {
    try {
      const response = await getPublishNoticePreview(api, props.kind, id)
      publishPreview.value = noticePreview(response)
      if (!publishPreview.value) publishPreviewError.value = "暂时无法预览发布通知。"
    } catch (error) {
      publishPreviewError.value = error instanceof Error ? error.message : "暂时无法预览发布通知。"
    }
  }
}

onMounted(load)
</script>

<template>
  <AdminPage :title="`${actionLabel(action, kind)}：${name ?? ''}`" section="activities" :back-href="activityHref(kind)">
    <p v-if="loading" role="status">正在加载…</p>
    <AdminNotice v-else-if="loadError" :message="loadError" kind="error" />
    <form v-else class="b-form" @submit.prevent="mutation.submit({ reason, announce, preview_version: publishPreview?.preview_version ?? '' })">
      <section class="b-section">
        <dl class="b-kv">
          <dt>{{ activityLabel(kind) }}</dt><dd>{{ name }}</dd>
          <dt>当前状态</dt><dd>{{ statusLabel(status ?? '') }}</dd>
          <template v-if="kind === 'tournaments'">
            <dt>报名时间</dt>
            <dd>{{ timestamp(tournament?.tournament?.registration_opens_at) }} 至 {{ timestamp(tournament?.tournament?.registration_closes_at) }}</dd>
          </template>
          <template v-else>
            <dt>开始时间</dt><dd>{{ timestamp(scrim?.scrim?.starts_at) }}</dd>
            <dt>报名截止</dt><dd>{{ timestamp(scrim?.row?.signup_deadline) }}</dd>
            <dt>已报名</dt><dd>{{ scrim?.row?.signup_total ?? 0 }} 人</dd>
          </template>
        </dl>
        <p v-if="action === 'cancel'" class="b-section__text">
          取消后{{ activityLabel(kind) }}从列表中消失，详情页仍可访问并显示「已取消」。取消后问你要不要给{{ kind === 'tournaments' ? '已报名的队长' : '已报名的人' }}发信。
        </p>
        <p v-if="action === 'delete'" class="b-section__text">删除后无法恢复。</p>
        <ActivityField v-if="kind === 'tournaments' && action === 'cancel'" id="reason" label="说明（发信的话会写进信里）" :errors="fields.reason" v-slot="field">
          <input
            id="reason"
            v-model="reason"
            class="c-input"
            type="text"
            name="reason"
            maxlength="300"
            :disabled="pending || uncertain"
            :aria-describedby="field.describedby"
            :aria-invalid="Boolean(fields.reason?.length)"
          >
        </ActivityField>
      </section>
      <div v-if="action === 'publish' && missing.length" class="c-notice c-notice--warn" data-publish-missing><CIcon name="alert" /><div class="c-notice__body">还没填好：{{ missing.join('、') }}。<RouterLink class="c-link" :to="activityHref(kind, id)">去填</RouterLink>，填好再发布。</div></div>
      <AdminNotice v-else-if="unavailable" message="当前状态不能执行这个操作，请重新打开页面。" kind="warn" />
      <fieldset v-if="action === 'publish' && publishPreview" class="b-fieldset">
        <legend class="b-fieldset__legend">活动通知</legend>
        <AdminNotice v-if="publishPreview.problem" :message="`发布后不能马上通知全体成员：${publishPreview.problem}`" kind="warn" />
        <div v-else class="c-field">
          <label class="c-check">
            <input v-model="announce" type="checkbox" name="announce" value="1" :disabled="pending || uncertain || !publishPreview.recipients">
            <span>发布后同时通知全体成员（{{ publishPreview.recipients }} 人）</span>
          </label>
          <div class="c-field__help">发给开着「活动通知」的成员。不勾也可以之后在列表的「更多」里发，发之前能看到信的样子；以后有修改还可以再发。</div>
        </div>
      </fieldset>
      <AdminNotice v-if="action === 'publish' && publishPreviewError" :message="publishPreviewError" kind="warn" />
      <AdminNotice v-if="message" :message="message" kind="error" />
      <div class="b-actions">
        <button
          type="submit"
          class="c-btn"
          :class="action === 'cancel' || action === 'delete' ? 'c-btn--danger' : 'c-btn--primary'"
          :disabled="pending || uncertain || unavailable"
        >{{ pending ? '正在提交…' : actionLabel(action, kind) }}</button>
        <button v-if="uncertain" type="button" class="c-btn c-btn--secondary" :disabled="pending" @click="mutation.retry()">重试上次提交</button>
        <button v-if="message && !uncertain && !pending" type="button" class="c-btn c-btn--secondary" @click="load">刷新确认页</button>
        <RouterLink class="c-btn c-btn--secondary" :to="activityHref(kind)">返回</RouterLink>
      </div>
    </form>
    <button v-if="loadError" type="button" class="c-btn c-btn--secondary" @click="load">重试</button>
  </AdminPage>
</template>
