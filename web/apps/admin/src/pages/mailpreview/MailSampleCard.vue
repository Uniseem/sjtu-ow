<script setup lang="ts">
import { computed, ref } from "vue"
import { sampleDocumentURL, type MailSample } from "./pending"
const props = withDefaults(defineProps<{ sample: MailSample; detail?: boolean }>(), { detail: false })
const narrow = ref(false)
const mode = ref<"html" | "text">("html")
const htmlURL = computed(() => sampleDocumentURL(props.sample, "preview"))
const textURL = computed(() => sampleDocumentURL(props.sample, "text"))
const iframe = ref<HTMLIFrameElement | null>(null)
const copied = ref(false)
const message = ref("")
let copyGeneration = 0

async function copy(): Promise<void> {
  const generation = ++copyGeneration
  message.value = ""
  copied.value = false
  try {
    await navigator.clipboard.writeText(props.sample.text)
    if (generation === copyGeneration) copied.value = true
  } catch {
    if (generation === copyGeneration) message.value = "暂时无法复制，请选中下面的纯文本手动复制。"
  }
}
function reload(): void {
  if (!iframe.value || !htmlURL.value) return
  iframe.value.src = htmlURL.value
}
</script>
<template>
  <article class="b-section" :data-mail-sample="sample.key" :aria-labelledby="`sample-${sample.key}`">
    <div class="c-panel__head">
      <h2 v-if="detail" :id="`sample-${sample.key}`" class="b-section__title">{{ sample.title }}</h2>
      <h3 v-else :id="`sample-${sample.key}`" class="text-lg font-semibold">
        <RouterLink class="c-link" :to="`/admin/settings/email-samples/${sample.key}/`">{{ sample.title }}</RouterLink>
      </h3>
      <RouterLink v-if="!detail" class="c-btn c-btn--quiet c-btn--sm" :to="`/admin/settings/email-samples/${sample.key}/`">单独查看</RouterLink>
    </div>
    <dl class="c-facts c-panel">
      <dt>收件人</dt><dd>{{ sample.to }}</dd>
      <dt>主题</dt><dd>{{ sample.subject }}</dd>
      <dt>带前缀的主题</dt><dd>{{ sample.delivered_subject }}</dd>
      <dt v-if="detail">样张日期</dt><dd v-if="detail">{{ sample.date }}</dd>
    </dl>
    <p v-if="!sample.fictional" class="c-notice c-notice--error" role="alert">样张缺少虚构数据标记，暂不显示信件。</p>
    <template v-else>
      <div v-if="detail" class="b-rowacts" role="group" aria-label="样张显示方式">
        <button type="button" class="c-btn c-btn--secondary c-btn--sm" :aria-pressed="mode === 'html'" @click="mode = 'html'">HTML 版</button>
        <button type="button" class="c-btn c-btn--secondary c-btn--sm" :aria-pressed="mode === 'text'" @click="mode = 'text'">纯文本版</button>
        <label class="c-check"><input v-model="narrow" type="checkbox">窄屏预览</label>
        <button v-if="mode === 'html'" type="button" class="c-btn c-btn--quiet c-btn--sm" @click="reload">重新加载</button>
      </div>
      <iframe
        v-if="htmlURL && (!detail || mode === 'html')"
        ref="iframe"
        :src="htmlURL"
        class="c-mailframe"
        :class="{ 'max-w-sm': narrow }"
        :title="`${sample.title}的 HTML 版`"
        loading="lazy"
        sandbox=""
        referrerpolicy="no-referrer"
      />
      <p v-else-if="!htmlURL" class="c-notice c-notice--error" role="alert">邮件样张地址无效。</p>
      <template v-if="detail && mode === 'text'">
        <pre class="c-mailtext" tabindex="0">{{ sample.text }}</pre>
      </template>
      <details v-else-if="!detail">
        <summary class="cursor-pointer text-fg-2">纯文本版</summary>
        <pre class="c-mailtext" tabindex="0">{{ sample.text }}</pre>
      </details>
      <div v-if="detail" class="b-rowacts">
        <a v-if="htmlURL" class="c-btn c-btn--secondary c-btn--sm" :href="htmlURL" target="_blank" rel="noopener noreferrer">新窗口打开 HTML</a>
        <a v-if="textURL" class="c-btn c-btn--secondary c-btn--sm" :href="textURL" target="_blank" rel="noopener noreferrer">新窗口打开纯文本</a>
        <button type="button" class="c-btn c-btn--quiet c-btn--sm" @click="copy">{{ copied ? '已复制' : '复制纯文本' }}</button>
      </div>
      <p v-if="copied" class="b-sub" role="status">纯文本已复制。</p>
      <p v-if="message" class="c-notice c-notice--error" role="alert">{{ message }}</p>
    </template>
  </article>
</template>
