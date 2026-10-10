<script setup lang="ts">
import { ref, watch } from "vue"
import type { CommentSubmission } from "./types"

// comments/templates/comments/_composer.html in its three forms: the top
// composer (写评论), a reply (回复 …), and the edit form (修改评论, prefilled).
// Only ever rendered for a signed-in visitor (design 13.13.3).
const props = defineProps<{ parentName?: string; editing?: boolean; draft?: string }>()
const emit = defineEmits<{ send: [CommentSubmission] }>()
const pending = ref(false)
const form = ref<HTMLFormElement | null>(null)
const body = ref(props.draft ?? "")
watch(() => props.draft, (value) => { body.value = value ?? "" })

function submit() {
  // Go strips and rejects empty content; the required attribute alone lets
  // whitespace through, so trim here as comments/services.py create does.
  if (pending.value) return
  const text = body.value.trim()
  if (!text) return
  pending.value = true
  emit("send", {
    content: text,
    complete(success) {
      pending.value = false
      if (!success) return
      if (!props.editing) body.value = ""
      // Like the old whole-section swap, a completed reply/edit folds away.
      form.value?.closest("details")?.removeAttribute("open")
    },
  })
}
</script>
<template>
  <!-- The edit form's textarea carries its own aria-label (comments/_own.html);
       the write forms wrap theirs in a labelled span (comments/_composer.html). -->
  <form ref="form" class="c-composer" :aria-busy="pending ? 'true' : undefined" @submit.prevent="submit">
    <label v-if="!editing">
      <span class="sr-only">{{ parentName ? `回复 ${parentName}` : "写评论" }}</span>
      <textarea v-model="body" name="body" rows="3" maxlength="500" required :disabled="pending" class="c-input" :placeholder="parentName ? `回复 ${parentName}…` : '说点什么…（最多 500 字）'"></textarea>
    </label>
    <textarea v-else v-model="body" name="body" rows="3" maxlength="500" required :disabled="pending" class="c-input" aria-label="修改评论"></textarea>
    <div class="c-composer__bar">
      <button type="submit" :disabled="pending" class="c-btn c-btn--primary c-btn--sm">{{ editing ? "保存修改" : parentName ? "回复" : "发表评论" }}</button>
      <span v-if="!editing">发出即显示；违规内容会被内容编辑隐藏。</span>
    </div>
  </form>
</template>
