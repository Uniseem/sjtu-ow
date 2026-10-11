<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiLettersBatch } from "@sjtu-ow/api"
import { PageRedirect } from "@sjtu-ow/shared/navigation"
import { letterBatch, returnFromLetters } from "../letters"
import { readLetterBatch } from "../letter-schema"

export async function load(ctx: LoadCtx) {
  const batch = letterBatch(ctx.params.batch)
  const result = readLetterBatch(await getApiLettersBatch(ctx.api, batch), batch)
  const back = returnFromLetters(ctx.query.back || result.back)
  if (result.state !== "waiting") throw new PageRedirect(back)
  return { title: "发信", batch: result, back }
}
</script>

<script setup lang="ts">
import { computed, inject, ref, watch } from "vue"
import { useHead } from "@unhead/vue"
import { postApiLettersBatch } from "@sjtu-ow/api"
import type { PostApiLettersBatchIn } from "@sjtu-ow/api"
import LettersLayout from "../components/LettersLayout.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import { requirePageData } from "../personal"
import { previewURL } from "../letters"
import type { PersonalLetterBatch } from "../letters"
import { finishAccountAction } from "../account-form"

const data = requirePageData(inject<{ batch: PersonalLetterBatch; back: string }>("page-data"))
const api = useApi()
const selected = ref(data.batch.letters.map((letter) => letter.id))
const previews = computed(() => new Map(data.batch.letters.map((letter) => [
  letter.id,
  previewURL(letter.preview_url, data.batch.batch, letter.id),
])))
const hasAllPreviews = computed(() => data.batch.letters.every((letter) => previews.value.get(letter.id)))

const mutation = useMutation(
  (attempt: { batch: string; body: PostApiLettersBatchIn }, extras) => postApiLettersBatch(api, attempt.batch, attempt.body, extras),
  () => finishAccountAction(returnFromLetters(data.back)),
)

function submit(event: SubmitEvent): void {
  const skip = event.submitter instanceof HTMLButtonElement
    && event.submitter.name === "skip" && event.submitter.value === "1"
  send(skip)
}

function send(skip: boolean): void {
  if (!skip && !hasAllPreviews.value) return
  const allowed = new Set(data.batch.letters.map((letter) => letter.id))
  const ids = [...new Set(selected.value)].filter((id) => allowed.has(id))
  void mutation.submit({
    batch: data.batch.batch,
    body: { send: skip ? [] : ids, skip },
  })
}

watch(() => data.batch.batch, () => {
  selected.value = data.batch.letters.map((letter) => letter.id)
  mutation.clear()
})

useHead({ title: "发信 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })
</script>

<template>
  <LettersLayout
    title="发信"
    heading="要不要发信"
    lede="刚才的操作已经完成。它要发下面这些信：勾上的发出去，不勾的不发。"
  >
    <form
      method="post"
      class="c-form"
      data-held-letters
      :aria-busy="mutation.pending.value || undefined"
      @submit.prevent="submit"
    >
      <CMutationError
        :message="mutation.message.value"
        :uncertain="mutation.uncertain.value"
        :pending="mutation.pending.value"
        @retry="mutation.retry"
      />
      <section
        v-for="(letter, index) in data.batch.letters"
        :key="letter.id"
        class="c-step"
        :data-held-letter="letter.id"
      >
        <label class="c-check font-semibold">
          <input
            v-model="selected"
            type="checkbox"
            name="send"
            :value="letter.id"
            :disabled="mutation.pending.value || mutation.uncertain.value"
          >发这封信
        </label>
        <dl class="c-facts">
          <dt>发给</dt>
          <dd>{{ letter.who }}<template v-if="letter.count > 1">（{{ letter.count }} 人，每人一封）</template></dd>
          <dt>主题</dt>
          <dd>{{ letter.subject }}</dd>
        </dl>
        <details :open="index === 0">
          <summary class="cursor-pointer text-fg-2">信的样子</summary>
          <iframe
            v-if="previews.get(letter.id)"
            class="c-mailframe mt-3"
            :src="previews.get(letter.id) ?? undefined"
            :title="'「' + letter.subject + '」的样子'"
            loading="lazy"
            sandbox=""
            referrerpolicy="no-referrer"
          />
          <p v-else class="mt-3 text-sm text-fg-2" role="status">信件预览暂时无法打开，请稍后再试。</p>
        </details>
      </section>
      <div class="c-formbar">
        <button
          type="submit"
          class="c-btn c-btn--primary"
          :disabled="!mutation.canStart.value || !hasAllPreviews"
        >发出勾选的信</button>
        <button
          type="submit"
          name="skip"
          value="1"
          class="c-btn c-btn--secondary"
          :disabled="!mutation.canStart.value"
        >都不发</button>
      </div>
    </form>
  </LettersLayout>
</template>
