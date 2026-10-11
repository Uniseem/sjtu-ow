<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiLetters, getApiLettersBatch, postApiLettersBatch } from "@sjtu-ow/api"
import type { GetApiLettersOut } from "@sjtu-ow/api"
import { letterBatch, letterDate, previewURL, returnFromLetters, waitingURL, type PersonalLetterBatch } from "@sjtu-ow/shared/letters"
import { readLetterBatch, readWaitingLetters } from "@sjtu-ow/shared/letter-schema"
import AdminPage from "../../components/AdminPage.vue"
import AdminNotice from "../../components/AdminNotice.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useAdminSession } from "../../core/session"
const route = useRoute()
const router = useRouter()
const api = useAdminApi()
const session = useAdminSession()
const waiting = ref<GetApiLettersOut | null>(null)
const batch = ref<PersonalLetterBatch | null>(null)
const selected = ref<number[]>([])
const loading = ref(false)
const error = ref("")
let generation = 0
const previews = computed(() => new Map((batch.value?.letters || []).map(letter => [letter.id, previewURL(letter.preview_url, batch.value?.batch || "", letter.id)])))
const complete = computed(() => Boolean(batch.value?.letters.length && batch.value.letters.every(letter => Boolean(previews.value.get(letter.id)))))
function back(): string {
  const query = Array.isArray(route.query.back) ? route.query.back[0] : route.query.back
  const destination = returnFromLetters(query || batch.value?.back)
  return destination === "/letters/" ? "/admin/letters/" : destination
}
const action = useAdminAction((body: { batch: string; send: number[]; skip: boolean }, extras) => postApiLettersBatch(api, body.batch, { send: body.send, skip: body.skip }, extras), async () => {
  const destination = back()
  await session.refresh()
  if (destination.startsWith("/admin/")) await router.push(destination)
  else window.location.assign(destination)
})
async function load(): Promise<void> {
  const current = ++generation
  loading.value = true
  error.value = ""
  try {
    const rawBatch = route.params.batch
    if (typeof rawBatch === "string") {
      const key = letterBatch(rawBatch)
      const result = readLetterBatch(await getApiLettersBatch(api,key,{ unauthorized:"throw" }),key)
      if (current !== generation) return
      batch.value = result
      waiting.value = null
      selected.value = result.letters.map(letter => letter.id)
      if (result.state !== "waiting") await router.replace(back())
    } else {
      const result = readWaitingLetters(await getApiLetters(api,{ unauthorized:"throw" }))
      if (current !== generation) return
      waiting.value = result
      batch.value = null
    }
  } catch (failure) { if (current === generation) error.value = failure instanceof Error ? failure.message : "信件没有加载完成。" }
  finally { if (current === generation) loading.value = false }
}
function submit(skip: boolean): void {
  if (!batch.value || !skip && !complete.value) return
  const allowed = new Set(batch.value.letters.map(letter => letter.id))
  void action.submit({ batch:batch.value.batch,send:skip ? [] : [...new Set(selected.value)].filter(id => allowed.has(id)),skip })
}
watch(() => route.fullPath, () => { action.clear(); void load() }, { immediate: true })
</script>
<template>
  <AdminPage :title="batch ? '要不要发信' : '还没发的信'" section="home">
    <p v-if="loading" role="status" class="b-section__text">正在读信…</p>
    <AdminNotice v-if="error" :message="error" kind="error" />
    <button v-if="error" type="button" class="c-btn c-btn--secondary" @click="load">重新打开</button>
    <template v-if="waiting">
      <p class="b-section__text">做完事以后没决定发不发的信。等满 7 天作废。</p>
      <ul v-if="waiting.batches.length" class="flex flex-col gap-4" data-held-batches>
        <li v-for="item in waiting.batches" :key="item.batch" class="c-panel flex flex-wrap items-center justify-between gap-3">
          <div class="min-w-0"><p class="font-semibold">{{ item.subjects.join('；') }}</p><p class="text-sm text-fg-2">{{ letterDate(item.at) }} · {{ item.people }} 人</p></div>
          <a class="c-btn c-btn--secondary" :href="waitingURL(item.batch, item.in_back_office)">看信</a>
        </li>
      </ul>
      <CEmpty v-else title="没有等着发的信" message="做完事要发的信都处理过了。" />
    </template>
    <template v-if="batch && batch.state === 'waiting'">
      <p class="b-section__text">刚才的操作已经完成。它要发下面这些信：勾上的发出去，不勾的不发。</p>
      <form method="post" class="b-form" data-held-letters :aria-busy="action.pending.value || undefined" @submit.prevent="submit(false)">
        <CMutationError :message="action.message.value" :uncertain="action.uncertain.value" :pending="action.pending.value" @retry="action.retry" />
        <section v-for="(letter,index) in batch.letters" :key="letter.id" class="b-section" :data-held-letter="letter.id">
          <label class="c-check font-semibold"><input v-model="selected" type="checkbox" name="send" :value="letter.id" :disabled="!action.canStart.value">发这封信</label>
          <dl class="b-kv"><dt>发给</dt><dd>{{ letter.who }}<template v-if="letter.count > 1">（{{ letter.count }} 人，每人一封）</template></dd><dt>主题</dt><dd>{{ letter.subject }}</dd></dl>
          <details :open="index === 0"><summary class="cursor-pointer text-fg-2">信的样子</summary><iframe v-if="previews.get(letter.id)" class="c-mailframe mt-3" :src="previews.get(letter.id) || undefined" :title="'「' + letter.subject + '」的样子'" loading="lazy" sandbox="" referrerpolicy="no-referrer" /><p v-else class="mt-3 text-sm text-fg-2">信件预览暂时无法打开，请重新打开页面。</p></details>
        </section>
        <div class="b-actions"><button type="submit" class="c-btn c-btn--primary" :disabled="!action.canStart.value || !complete">发出勾选的信</button><button type="button" class="c-btn c-btn--secondary" :disabled="!action.canStart.value" @click="submit(true)">都不发</button></div>
      </form>
    </template>
  </AdminPage>
</template>
