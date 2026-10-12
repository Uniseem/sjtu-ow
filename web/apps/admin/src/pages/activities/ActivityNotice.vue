<script setup lang="ts">
import { showReadError } from "../../core/read-error"
import { computed, onMounted, onUnmounted, shallowRef, watch } from "vue"
import { useRoute } from "vue-router"
import { ApiError } from "@sjtu-ow/api"
import type { GetApiAdminAnnounceKindIdOut } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import AdminPage from "../../components/AdminPage.vue"
import AdminNotice from "../../components/AdminNotice.vue"
import ActivityField from "../../components/activities/ActivityField.vue"
import { activityHref, numericId, queryText, noticeTime } from "./domain"
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
const note = shallowRef("")
const noteRevision = shallowRef(0)
const previewRevision = shallowRef(-1)
let noteTimer: ReturnType<typeof setTimeout> | undefined
let sequence = 0
let request: AbortController | null = null
const title = computed(() => audience.value === "participants" ? "通知报名的人" : "通知全体成员")
const mutation = useAdminAction<{ audience: "all" | "participants"; preview_version: string; note: string }, { recipients: number; waiting: boolean }>(
  (body, extras) => sendActivityNotice(api, singular.value, id, body, extras),
  async (result) => {
    sent.value = result.waiting ? `已排入待发送队列，共 ${result.recipients} 人。` : `已安排发送，共 ${result.recipients} 人。`
    await load()
  },
)
const { pending, message, uncertain, fields } = mutation
const canSend = computed(() => {
  return preview.value !== null && !preview.value.problem
    && preview.value.recipients > 0 && preview.value.audience === audience.value
    && previewRevision.value === noteRevision.value && !error.value
    && !loading.value && !pending.value && !uncertain.value
})

async function load(): Promise<void> {
  request?.abort()
  request = new AbortController()
  const token = ++sequence
  const revision = noteRevision.value
  const requestedNote = note.value
  loading.value = true
  error.value = ""
  history.value = []
  try {
    if (!id) throw new ApiError(404, "not_found", "找不到这个页面")
    const result = await getActivityNotice(api, singular.value, id, audience.value, { signal: request.signal }, requestedNote)
    if (sequence !== token || revision !== noteRevision.value) return
    history.value = result.history
    const parsed = noticePreview(result)
    if (parsed?.audience === audience.value) {
      preview.value = parsed
      previewRevision.value = revision
    }
    else error.value = "暂时无法预览这封通知，请稍后再试。"
  } catch (failure) {
    if (sequence !== token || revision !== noteRevision.value || request.signal.aborted) return
    showReadError(failure)
    error.value = failure instanceof Error ? failure.message : "暂时无法预览这封通知，请稍后再试。"
  } finally {
    if (sequence === token) loading.value = false
  }
}

function send(): void {
  if (!canSend.value || !preview.value) return
  if (!window.confirm(`给 ${preview.value.recipients} 人发这封信？`)) return
  void mutation.submit({ audience: preview.value.audience, preview_version: preview.value.preview_version, note: note.value })
}

function editNote(event: Event): void {
  if (!(event.target instanceof HTMLTextAreaElement)) return
  note.value = event.target.value
  noteRevision.value += 1
  if (noteTimer !== undefined) clearTimeout(noteTimer)
  noteTimer = setTimeout(() => { void load() }, 250)
}

watch(() => audience.value, () => { note.value = ""; noteRevision.value += 1; void load() })
onMounted(load)
onUnmounted(() => { sequence += 1; request?.abort(); if (noteTimer !== undefined) clearTimeout(noteTimer) })
</script>

<template>
  <AdminPage :title="`${title}：${preview?.object_title ?? ''}`" section="events" :back-href="activityHref(kind)">
    <AdminNotice v-if="sent" :message="sent" kind="ok" />
    <p v-if="loading" role="status">正在加载预览…</p>
    <AdminNotice v-if="error" :message="error" kind="error" />
    <div v-if="preview" class="b-split">
      <section class="b-section">
        <h2 class="b-section__title">信的正文（预览）</h2>
        <p class="b-section__text">每人一封、互相看不到；{{ audience === 'participants' ? '写的说明会放进「管理员的说明」一段。' : '底部有各自的退订链接。' }}下面是写给你自己的样子。</p>
        <pre class="b-letter">{{ preview.body_text }}</pre>
      </section>
      <aside class="b-aside">
        <section class="b-section">
          <dl class="b-kv">
            <dt>内容</dt><dd>{{ preview.object_title }}</dd>
            <dt>收信的人</dt><dd>{{ preview.recipients }} 人（{{ audience === 'participants' ? (kind === 'tournaments' ? '有效名单里的人和散人池里的人；和本人报的活动有关，不看「活动通知」开关' : '全部报名者；和本人报的活动有关，不看「活动通知」开关') : `在用、邮箱已验证、开着「活动通知」的成员${preview.sjtu_only ? '，只发交大成员' : ''}` }}）</dd>
            <dt>主题</dt><dd>{{ preview.subject }}</dd>
            <template v-if="history.length"><dt>发过</dt><dd data-announce-history>{{ history.length }} 次，上次 {{ noticeTime(history[0]?.created_at) }} 发给 {{ history[0]?.recipient_count }} 人（{{ history[0]?.audience === 'participants' ? '报名的人' : '全体成员' }}）</dd></template>
          </dl>
          <AdminNotice v-if="preview.moved_from" :message="`开始时间从 ${noticeTime(preview.moved_from)} 改到了 ${noticeTime(preview.starts_at)}，信里会写原来和现在的时间。`" kind="info" />
          <AdminNotice v-if="history.length && !preview.problem" :message="`之前发过 ${history.length} 次，这次信的开头会写明，并提醒以这封为准。`" kind="info" />
          <AdminNotice v-if="preview.problem" :message="preview.problem" kind="warn" />
          <p v-if="preview.will_wait" class="b-sub">本次通知会进入待发送队列。</p>
          <form class="b-form" @submit.prevent="send">
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
            <AdminNotice v-if="message" :message="message" kind="error" />
            <div class="b-actions">
              <button type="submit" class="c-btn c-btn--primary" :disabled="!canSend">{{ pending ? '正在发送…' : `发给 ${preview.recipients} 人` }}</button>
              <button v-if="uncertain" type="button" class="c-btn c-btn--secondary" :disabled="pending" @click="mutation.retry()">重试上次提交</button>
              <RouterLink class="c-btn c-btn--secondary" :to="activityHref(kind)">不发了</RouterLink>
            </div>
          </form>
        </section>
      </aside>
    </div>
    <button v-if="error" type="button" class="c-btn c-btn--secondary" @click="load">重试</button>
  </AdminPage>
</template>
