<script setup lang="ts">
import { onMounted, ref } from "vue"
import { formatContentTime } from "../../pages/content/types"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import { ApiError, getApiAdminArticles } from "@sjtu-ow/api"
import { readSaveReceipt } from "@sjtu-ow/shared/save-receipt"
import { useAdminApi } from "../../core/api"
import SaveStatus from "../SaveStatus.vue"
import ContentField from "./ContentField.vue"
import ContentActionMessage from "./ContentActionMessage.vue"
import DraftPublication from "./DraftPublication.vue"
import { useContentPermissions } from "../../pages/content/permissions"
import { useContentDraft } from "../../pages/content/use-draft"
import { readPinCurrent, validatePinValue } from "../../pages/content/pin-values"
import { publishHomeDraft, readHomeDraft, saveHomeDraft, type HomeDraftProjection } from "../../pages/content/pending"
import type { Article } from "../../pages/content/types"

const props = defineProps<{ detail: HomeDraftProjection }>()
const publicationState = ref({ live: props.detail.live, last_published_at: props.detail.last_published_at })
const api = useAdminApi()
const permission = useContentPermissions()
const articles = ref<Article[]>([])
const slots = ref<(number | null)[]>([...props.detail.draft.article_ids, null, null, null].slice(0, 3))
const loading = ref(false)
const loadMessage = ref("")
const draft = useContentDraft({
  initial: props.detail.draft,
  version: props.detail.version,
  unpublished: props.detail.has_unpublished_changes,
  available: () => permission.managePages.value,
  preview_url: props.detail.preview_url,
  readCurrent: readPinCurrent,
  transport: async (body, extras) => readSaveReceipt(await saveHomeDraft(api, body, extras), props.detail.draft, validatePinValue),
  publish: async (version, extras) => {
    const result = await publishHomeDraft(api, version, extras)
    publicationState.value = { live: result.live, last_published_at: result.last_published_at }
    return result
  },
  refresh: () => readHomeDraft(api),
})
const save = draft.save
function selected(index: number, event: Event): void {
  if (!(event.target instanceof HTMLSelectElement) || draft.blocked.value) return
  const id = event.target.value ? Number(event.target.value) : null
  slots.value[index] = id
  save.set("article_ids", slots.value.filter((value): value is number => value !== null), "choice")
}
async function loadArticles(): Promise<void> {
  loading.value = true
  loadMessage.value = ""
  try {
    const result: Article[] = []
    let page = 1
    let total = 0
    do {
      const response = await getApiAdminArticles(api, { status: "live", page, page_size: 100 })
      result.push(...response.items.filter((item): item is Article => item !== null && item.live))
      total = response.total
      page += 1
      if (response.items.length === 0) break
    } while ((page - 1) * 100 < total)
    articles.value = result.sort((a, b) => (b.first_published_at ?? "").localeCompare(a.first_published_at ?? ""))
  } catch (cause) {
    loadMessage.value = cause instanceof ApiError ? cause.message : "置顶文章暂时无法加载，请稍后再试。"
  } finally {
    loading.value = false
  }
}
onMounted(() => { void loadArticles() })
</script>
<template>
  <div class="b-split">
    <form class="b-form" novalidate @submit.prevent="save.save">
      <SaveStatus idle-message="改了就自动存成草稿，点「发布」才上线" :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
      <p v-if="draft.notice.value" class="c-notice c-notice--info" role="status">{{ draft.notice.value }}</p>
      <ContentActionMessage :message="draft.publication.message.value" :pending="draft.publication.pending.value" :uncertain="draft.publication.uncertain.value" @retry="draft.publication.retry" />
      <fieldset class="b-fieldset" :disabled="!permission.managePages.value || draft.blocked.value">
        <p class="b-section__text">最多 3 篇，按这里的顺序排在首页最上面。只能选已经发布的文章。改了自动存成草稿，点「发布」首页才更新。</p>
        <p v-if="loading" class="b-sub" role="status">正在加载置顶文章…</p>
        <div v-if="loadMessage" class="c-notice c-notice--error" role="alert"><p>{{ loadMessage }}</p><button type="button" class="c-btn c-btn--secondary c-btn--sm" @click="loadArticles">重新加载</button></div>
        <ContentField v-for="(_, index) in slots" :key="index" :name="`article_${index + 1}`" :label="`第 ${index + 1} 篇`">
          <template #default="field"><select :id="field.id" class="c-input" :name="`article_${index + 1}`" :value="slots[index] ?? ''" @change="selected(index, $event)"><option value="">（不置顶）</option><option v-for="article in articles" :key="article.id" :value="article.id">{{ article.title }}</option></select></template>
        </ContentField>
        <ul v-if="save.fields.value.article_ids?.length" class="c-field__error" role="alert"><li v-for="message in save.fields.value.article_ids" :key="message">{{ message }}</li></ul>
      </fieldset>
      <div class="b-formbar">
        <button v-if="detail.can_publish" type="submit" name="publish" value="1" class="c-btn c-btn--primary" :disabled="!draft.publication.canStart.value || save.pending.value" @click.prevent="draft.prepare">发布</button>
        <button type="submit" name="save" value="1" class="c-btn c-btn--secondary" hidden :disabled="!permission.managePages.value || draft.blocked.value || save.pending.value">保存草稿</button>
      </div>
      <DraftPublication v-if="draft.confirmation.value" title="首页置顶" :pending="draft.publication.pending.value" @confirm="draft.publish" @cancel="draft.confirmation.value = false" />
    </form>
    <aside class="b-aside" aria-label="状态">
      <section class="b-section"><h2 class="b-section__title">状态</h2><dl class="b-kv"><dt>状态</dt><dd data-draft-status><CStatus :label="publicationState.live ? draft.unpublished.value || save.dirty.value ? '已发布·有改动' : '已发布' : '草稿'" :kind="publicationState.live ? draft.unpublished.value || save.dirty.value ? 'warn' : 'ok' : 'done'" /></dd><template v-if="publicationState.last_published_at"><dt>最后发布</dt><dd>{{ formatContentTime(publicationState.last_published_at) }}</dd></template></dl><p class="b-section__text">「有改动」是说草稿里有还没发布的改动；网站上还是上次发布的样子。</p></section>
    </aside>
  </div>
</template>
