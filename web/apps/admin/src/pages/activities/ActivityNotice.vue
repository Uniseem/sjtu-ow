<script setup lang="ts">
import { computed, onMounted, onUnmounted, shallowRef, watch } from "vue"
import { useRoute } from "vue-router"
import { ApiError } from "@sjtu-ow/api"
import type { GetApiAdminAnnounceKindIdOut } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import AdminPage from "../../components/AdminPage.vue"
import AdminNotice from "../../components/AdminNotice.vue"
import ActivityField from "../../components/activities/ActivityField.vue"
import { activityHref, numericId, queryText, timestamp } from "./domain"
import type { ActivityKind } from "./domain"
import { getActivityNotice, noticePreview, sendActivityNotice } from "./pending"
import type { ActivityNoticePreview } from "./pending"

const props = defineProps<{ kind: ActivityKind }>()
const api = useAdminApi()
const route = useRoute()
const id = numericId(route.params.id)
const singular = computed(() => props.kind === "tournaments" ? "tournament" : "scrim")
const audience = computed<"all" | "participants"> (() => queryText(route.query.to) === "participants" ? "participants" : "all")
const preview = shallowRef<ActivityNoticePreview | null>(null)
const history = shallowRef<GetApiAdminAnnounceKindIdOut["history"]>([])
const loading = shallowRef(true)
const error = shallowRef("")
const sent = shallowRef("")
const confirm = shallowRef(false)
const note = shallowRef("")
let noteTimer: ReturnType<typeof setTimeout> | undefined
let sequence = 0
let request: AbortController | null = null
const title = computed(() => audience.value === "participants" ? "通知报名的人" : "通知全体成员")
const mutation = useAdminAction<{ audience: "all" | "participants"; preview_version: string; note: string }, { recipients: number; waiting: boolean }>(
  (body, extras) => sendActivityNotice(api, singular.value, id, body, extras),
  async (result) => {
    sent.value = result.waiting ? `已排入待发送队列，共 ${result.recipients} 人。` : `已安排发送，共 ${result.recipients} 人。`
    confirm.value = false
    await load()
  },
)
const { pending, message, uncertain, fields } = mutation
const canSend = computed(() => {
  return confirm.value && preview.value !== null && !preview.value.problem
    && preview.value.recipients > 0 && preview.value.audience === audience.value
    && !pending.value && !uncertain.value
})

async function load(): Promise<void> {
  request?.abort()
  request = new AbortController()
  const token = ++sequence
  loading.value = true
  error.value = ""
  preview.value = null
  history.value = []
  confirm.value = false
  try {
    if (!id) throw new ApiError(404, "not_found", "找不到这个页面")
    const result = await getActivityNotice(api, singular.value, id, audience.value, { signal: request.signal }, note.value)
    if (sequence !== token) return
    history.value = result.history
    const parsed = noticePreview(result)
    if (parsed?.audience === audience.value) preview.value = parsed
    else error.value = "暂时无法预览这封通知，请稍后再试。"
  } catch (failure) {
    if (sequence !== token || request.signal.aborted) return
    error.value = failure instanceof Error ? failure.message : "暂时无法预览这封通知，请稍后再试。"
  } finally {
    if (sequence === token) loading.value = false
  }
}

function send(): void {
  if (!canSend.value || !preview.value) return
  void mutation.submit({ audience: preview.value.audience, preview_version: preview.value.preview_version, note: note.value })
}

function editNote(event: Event): void {
  if (!(event.target instanceof HTMLTextAreaElement)) return
  note.value = event.target.value
  confirm.value = false
  preview.value = null
  if (noteTimer !== undefined) clearTimeout(noteTimer)
  noteTimer = setTimeout(() => { void load() }, 250)
}

watch(() => audience.value, () => { note.value = ""; void load() })
onMounted(load)
onUnmounted(() => { sequence += 1; request?.abort(); if (noteTimer !== undefined) clearTimeout(noteTimer) })
</script>

<template>
  <AdminPage :title="title" section="activities" :back-href="activityHref(kind)">
    <AdminNotice v-if="sent" :message="sent" kind="ok" />
    <ActivityField v-if="audience === 'participants'" id="announce-note" label="说明（选填）" :errors="fields.note" :help="`最多 ${preview?.note_max ?? 500} 字，放进信里「管理员的说明」一段。`" v-slot="field">
      <textarea
        id="announce-note"
        class="c-input"
        rows="4"
        :value="note"
        :maxlength="preview?.note_max ?? 500"
        :disabled="pending || uncertain"
        :aria-describedby="field.describedby"
        :aria-invalid="Boolean(fields.note?.length)"
        placeholder="比如：场地改到了线上，进群看房间号"
        @input="editNote"
      />
    </ActivityField>
    <p v-if="loading" role="status">正在加载预览…</p>
    <AdminNotice v-else-if="error" :message="error" kind="error" />
    <form v-else-if="preview" class="b-form" @submit.prevent="send">
      <section class="b-section">
        <h2 class="b-section__title">信的正文（预览）</h2>
        <p class="b-section__text">每人一封、互相看不到；{{ audience === 'participants' ? '写的说明会放进「管理员的说明」一段。' : '底部有各自的退订链接。' }}下面是写给你自己的样子。</p>
        <dl class="b-kv">
          <dt>收件人</dt><dd>{{ audience === 'participants' ? '报名的人' : '全体成员' }}</dd>
          <dt>收件人数</dt><dd>{{ preview.recipients }} 人</dd>
          <dt>主题</dt><dd>{{ preview.subject }}</dd>
        </dl>
        <iframe v-if="preview.preview_url" class="b-letter" width="100%" height="600" :src="preview.preview_url" title="信的正文（预览）" sandbox="" />
        <pre v-else class="b-letter">{{ preview.body_text }}</pre>
        <AdminNotice v-if="preview.problem" :message="preview.problem" kind="warn" />
        <p v-if="preview.will_wait" class="b-sub">本次通知会进入待发送队列。</p>
        <label class="c-check">
          <input v-model="confirm" type="checkbox" :disabled="pending || uncertain || Boolean(preview.problem)">
          已核对收件人和通知内容
        </label>
      </section>
      <AdminNotice v-if="message" :message="message" kind="error" />
      <div class="b-actions">
        <button type="submit" class="c-btn c-btn--primary" :disabled="!canSend">{{ pending ? '正在发送…' : `发给 ${preview.recipients} 人` }}</button>
        <button v-if="uncertain" type="button" class="c-btn c-btn--secondary" :disabled="pending" @click="mutation.retry()">重试上次提交</button>
        <RouterLink class="c-btn c-btn--secondary" :to="activityHref(kind)">不发了</RouterLink>
      </div>
    </form>
    <button v-if="error" type="button" class="c-btn c-btn--secondary" @click="load">重试</button>
    <section class="b-section">
      <h2 class="b-section__title">通知记录</h2>
      <table class="c-table c-table--stack">
        <thead><tr><th scope="col">时间</th><th scope="col">收件人</th><th scope="col">主题</th><th scope="col">人数</th><th scope="col">状态</th></tr></thead>
        <tbody>
          <tr v-for="item in history" :key="item.id">
            <td data-label="时间">{{ timestamp(item.created_at) }}</td>
            <td data-label="收件人">{{ item.audience === 'participants' ? '报名的人' : '全体成员' }}</td>
            <td data-label="主题">{{ item.subject }}</td>
            <td data-label="人数">{{ item.recipient_count }}</td>
            <td data-label="状态">{{ item.waiting ? '待发送' : '已发送' }}</td>
          </tr>
          <tr v-if="!history.length"><td colspan="5">还没有通知记录。</td></tr>
        </tbody>
      </table>
    </section>
  </AdminPage>
</template>
