<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue"
import { ApiError } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { createMarkdownPreview } from "../../pages/content/pending"
import { contentPreviewURL } from "../../pages/content/preview-url"

const props = defineProps<{ body: string; open: boolean }>()
const api = useAdminApi()
const pending = ref(false)
const message = ref("")
const url = ref<string | null>(null)
const source = ref("")
const stale = computed(() => Boolean(url.value && source.value !== props.body))
let controller: AbortController | null = null
let generation = 0
let disposed = false

async function load(): Promise<void> {
  controller?.abort()
  controller = new AbortController()
  const current = ++generation
  const body = props.body
  pending.value = true
  message.value = ""
  try {
    const result = await createMarkdownPreview(api, { body_md: body }, {
      signal: controller.signal,
      unauthorized: "throw",
    })
    if (disposed || current !== generation) return
    const safe = contentPreviewURL(result.preview_url)
    if (!safe) throw new ApiError(0, "invalid_preview", "预览地址无效，请重新生成。")
    url.value = safe
    source.value = body
  } catch (cause) {
    if (disposed || current !== generation || controller.signal.aborted) return
    message.value = cause instanceof ApiError ? cause.message : "暂时无法预览，请稍后再试。"
  } finally {
    if (!disposed && current === generation) pending.value = false
  }
}
watch(() => props.open, (open) => {
  if (open && (!url.value || stale.value)) void load()
}, { immediate: true })
onBeforeUnmount(() => { disposed = true; controller?.abort() })
</script>
<template>
  <section v-if="open" class="b-section" aria-label="正文预览">
    <p v-if="pending" class="b-sub" role="status">正在生成预览…</p>
    <p v-if="message" class="c-notice c-notice--error" role="alert">{{ message }}</p>
    <p v-if="stale" class="c-field__help">正文已修改，下面是上一份预览。</p>
    <button v-if="message || stale" type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="pending" @click="load">重新生成预览</button>
    <iframe v-if="url" :src="url" title="正文预览" class="w-full min-h-96 border-0" sandbox="allow-same-origin" />
  </section>
</template>
