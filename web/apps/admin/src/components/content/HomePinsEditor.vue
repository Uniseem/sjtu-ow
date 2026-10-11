<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { ApiError, getApiAdminArticlesId } from "@sjtu-ow/api"
import { readSaveReceipt } from "@sjtu-ow/shared/save-receipt"
import { useAdminApi } from "../../core/api"
import SaveStatus from "../SaveStatus.vue"
import ArticleChooser from "./ArticleChooser.vue"
import ContentActionMessage from "./ContentActionMessage.vue"
import DraftPublication from "./DraftPublication.vue"
import { useContentPermissions } from "../../pages/content/permissions"
import { useContentDraft } from "../../pages/content/use-draft"
import { readPinCurrent, validatePinValue } from "../../pages/content/pin-values"
import { publishHomeDraft, readHomeDraft, saveHomeDraft, type HomeDraftProjection } from "../../pages/content/pending"
import type { Article } from "../../pages/content/types"

const props = defineProps<{ detail: HomeDraftProjection }>()
const api = useAdminApi()
const permission = useContentPermissions()
const picker = ref(false)
const articles = ref<Map<number, Article>>(new Map())
const missingArticles = ref(new Set<number>())
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
  publish: (version, extras) => publishHomeDraft(api, version, extras),
  refresh: () => readHomeDraft(api),
})
const save = draft.save
const ids = computed(() => save.values.value.article_ids)
const canAdd = computed(() => ids.value.length < 3 && permission.managePages.value && !draft.blocked.value)
function selected(article: Article): void {
  if (!canAdd.value || !article.live || ids.value.includes(article.id)) return
  articles.value = new Map(articles.value).set(article.id, article)
  save.set("article_ids", [...ids.value, article.id], "choice")
  picker.value = false
}
function move(index: number, delta: number): void {
  const next = index + delta
  if (next < 0 || next >= ids.value.length || draft.blocked.value) return
  const order = [...ids.value]
  const id = order[index]
  if (id === undefined) return
  order.splice(index, 1)
  order.splice(next, 0, id)
  save.set("article_ids", order, "choice")
}
function remove(id: number): void {
  if (draft.blocked.value) return
  save.set("article_ids", ids.value.filter((value) => value !== id), "choice")
}
async function loadArticles(): Promise<void> {
  loading.value = true
  loadMessage.value = ""
  const result = new Map(articles.value)
  const missing = new Set<number>()
  try {
    // Three pins at most; permission-aware detail distinguishes missing from unpublished.
    for (const id of ids.value) {
      try {
        const detail = await getApiAdminArticlesId(api, id)
        if (detail.article) result.set(id, detail.article)
        else missing.add(id)
      } catch (cause) {
        if (cause instanceof ApiError && cause.status === 404) missing.add(id)
        else throw cause
      }
    }
    articles.value = result
    missingArticles.value = missing
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
      <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
      <p v-if="draft.notice.value" class="c-notice c-notice--info" role="status">{{ draft.notice.value }}</p>
      <ContentActionMessage :message="draft.publication.message.value" :pending="draft.publication.pending.value" :uncertain="draft.publication.uncertain.value" @retry="draft.publication.retry" />
      <fieldset class="b-fieldset" :disabled="!permission.managePages.value || draft.blocked.value">
        <legend class="b-section__title">置顶文章</legend>
        <p class="b-section__text">最多 3 篇，从已发布的文章里选，按这里的顺序显示。改了存成首页的草稿，「发布」才更新首页。</p>
        <p v-if="loading" class="b-sub" role="status">正在加载置顶文章…</p>
        <div v-if="loadMessage" class="c-notice c-notice--error" role="alert"><p>{{ loadMessage }}</p><button type="button" class="c-btn c-btn--secondary c-btn--sm" @click="loadArticles">重新加载</button></div>
        <ol v-if="ids.length" class="b-list">
          <li v-for="(id, index) in ids" :key="id">
            <div class="c-panel__head">
              <span>{{ index + 1 }}. {{ articles.get(id)?.title || (missingArticles.has(id) ? '文章不存在' : `文章 #${id}`) }}</span>
              <div class="b-rowacts">
                <button type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="index === 0" :aria-label="`上移${articles.get(id)?.title || '文章'}`" @click="move(index, -1)">上移</button>
                <button type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="index === ids.length - 1" :aria-label="`下移${articles.get(id)?.title || '文章'}`" @click="move(index, 1)">下移</button>
                <button type="button" class="c-btn c-btn--quiet c-btn--sm" @click="remove(id)">移除</button>
              </div>
            </div>
            <span v-if="articles.get(id) && !articles.get(id)?.live" class="b-sub">已撤下，首页不显示</span>
            <span v-if="missingArticles.has(id)" class="b-sub">文章已删除，请从置顶里移除。</span>
          </li>
        </ol>
        <p v-else class="b-section__text">没有置顶文章，首页按发布时间排。</p>
        <button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="!canAdd" @click="picker = true">选择文章</button>
        <ul v-if="save.fields.value.article_ids?.length" class="c-field__error" role="alert"><li v-for="message in save.fields.value.article_ids" :key="message">{{ message }}</li></ul>
      </fieldset>
      <div class="b-formbar">
        <button v-if="detail.can_publish" type="button" class="c-btn c-btn--primary" :disabled="!draft.publication.canStart.value || save.pending.value" @click="draft.prepare">发布</button>
        <button class="c-btn c-btn--secondary" :disabled="!permission.managePages.value || draft.blocked.value || save.pending.value">保存草稿</button>
        <button type="button" class="c-btn c-btn--quiet" :disabled="save.pending.value" @click="draft.openPreview">预览草稿</button>
      </div>
      <DraftPublication v-if="draft.confirmation.value" title="首页置顶" :pending="draft.publication.pending.value" @confirm="draft.publish" @cancel="draft.confirmation.value = false" />
    </form>
    <aside class="b-aside" aria-label="状态">
      <section class="b-section"><h2 class="b-section__title">状态</h2><dl class="b-kv"><dt>状态</dt><dd data-draft-status>{{ draft.unpublished.value || save.dirty.value ? '有改动还没发布' : '已发布' }}</dd></dl><p class="b-section__text">「有改动」是说草稿里有还没发布的改动；网站上还是上次发布的样子。</p><a class="c-btn c-btn--secondary c-btn--sm" href="/" target="_blank" rel="noopener">打开首页</a></section>
    </aside>
    <ArticleChooser v-if="picker" :excluded="ids" @select="selected" @close="picker = false" />
  </div>
</template>
