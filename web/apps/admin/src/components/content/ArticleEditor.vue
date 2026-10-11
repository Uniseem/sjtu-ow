<script setup lang="ts">
import { formatContentTime } from "../../pages/content/types"
import { computed, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import {
  ApiError, deleteApiArticlesId, patchApiArticlesId,
  postApiArticles, postApiArticlesIdPublish, postApiArticlesIdUnpublish,
} from "@sjtu-ow/api"
import { readSaveReceipt } from "@sjtu-ow/shared/save-receipt"
import { useAdminApi } from "../../core/api"
import { useAdminSave } from "../../core/use-save"
import { useAdminAction } from "../../core/use-action"
import SaveStatus from "../SaveStatus.vue"
import ContentField from "./ContentField.vue"
import ContentActionMessage from "./ContentActionMessage.vue"
import ConfirmContentAction from "./ConfirmContentAction.vue"
import ArticlePublication from "./ArticlePublication.vue"
import MarkdownEditor from "./MarkdownEditor.vue"
import ImageField from "./ImageField.vue"
import SubmissionGuide from "./SubmissionGuide.vue"
import { readArticleCurrent, validateArticleValue } from "../../pages/content/article-values"
import { useContentPermissions } from "../../pages/content/permissions"
import { readArticleEditor, type ArticleEditorProjection } from "../../pages/content/pending"
import { contentPreviewURL } from "../../pages/content/preview-url"
import { articleStatus, articleStatuses, draftFromArticle, emptyArticle, localDateTime, wireDateTime, type Article, type ArticleDraft, type Category } from "../../pages/content/types"

const props = defineProps<{ detail: ArticleEditorProjection | null; categories: Pick<Category, "id" | "name" | "allow_submission">[] }>()
const api = useAdminApi()
const router = useRouter()
const route = useRoute()
const permission = useContentPermissions()
const id = ref(props.detail?.article?.id ?? null)
const article = ref<Article | null>(props.detail?.article ?? null)
const initial = props.detail?.revision ?? (article.value ? draftFromArticle(article.value) : emptyArticle())
const draftChanged = ref(article.value?.has_unpublished_changes ?? false)
const publication = ref(false)
const destructive = ref<"unpublish" | "delete" | null>(null)
const notice = ref("")
const editor = ref<InstanceType<typeof MarkdownEditor> | null>(null)
const previewURL = computed(() => contentPreviewURL(props.detail?.preview_url))
const editable = computed(() => props.detail?.capabilities.edit ?? (!article.value || permission.canEdit(article.value)))
const canPublish = computed(() => props.detail?.capabilities.publish ?? (article.value ? permission.canPublish(article.value)
  : Boolean(permission.user.value?.superuser || permission.user.value?.caps.includes("articles.publish_own") || permission.everyArticle.value)))
const categories = computed(() => props.categories.filter((item) => !props.detail?.guide || item.allow_submission))
const creationVersions = new Map<string, number>()
const save: ReturnType<typeof useAdminSave<ArticleDraft>> = useAdminSave<ArticleDraft>({
  initial,
  version: props.detail?.version ?? 0,
  available: () => editable.value,
  readCurrent: (value) => readArticleCurrent(value, initial),
  transport: async (body, key, signal) => {
    let version = creationVersions.get(key) ?? body.base_version
    if (!id.value) {
      const draft = { ...initial, ...body.changes }
      const created = await postApiArticles(api, {
        title: draft.title,
        category_id: draft.category_id,
        summary: draft.summary,
        body_md: draft.body_md,
      }, { key: `${key}-create`, signal, unauthorized: "throw" })
      if (!Number.isSafeInteger(created.id) || created.id <= 0) throw new ApiError(0, "invalid_receipt", "草稿创建回执无效，请重试。")
      id.value = created.id
      version = created.version
      creationVersions.set(key, version)
    }
    const result = await patchApiArticlesId(api, id.value, {
      base_version: version,
      changes: body.changes,
    }, { key, signal, unauthorized: "throw" })
    const receipt = readSaveReceipt(result, initial, validateArticleValue)
    if (receipt.saved.length) draftChanged.value = true
    creationVersions.delete(key)
    return receipt
  },
})
watch(save.snapshot, (snapshot) => {
  if (id.value && route.params.id === undefined && !snapshot.dirty && !snapshot.saving && snapshot.state === "saved") {
    void router.replace(`/admin/articles/${id.value}/`)
  }
})
const values = save.values
const fields = save.fields

const publish = useAdminAction(
  (body: { id: number; base_version: number }, extras) => postApiArticlesIdPublish(api, body.id, { base_version: body.base_version }, extras),
  async (result) => {
    article.value = result.article
    draftChanged.value = false
    publication.value = false
    notice.value = result.article?.go_live_at && !result.article.live ? "已安排上线。" : "文章已发布。"
    if (id.value) {
      const current = await readArticleEditor(api, id.value)
      // Remount with the new committed version after publication.
      if (current.article) {
        save.controller.reset(current.revision ?? draftFromArticle(current.article), current.version)
        await router.replace(`/admin/articles/${current.article.id}/?published=${current.version}`)
      }
    }
  },
)
const destroy = useAdminAction(
  async (body: { id: number; kind: "unpublish" | "delete" }, extras) => {
    const result = body.kind === "delete" ? await deleteApiArticlesId(api, body.id, extras) : await postApiArticlesIdUnpublish(api, body.id, extras)
    return { kind: body.kind, result }
  },
  async (result) => {
    const kind = result.kind
    destructive.value = null
    if (kind === "delete") await router.push("/admin/articles/")
    else {
      if (id.value) {
        const current = await readArticleEditor(api, id.value)
        article.value = current.article
        if (current.article) save.controller.reset(current.revision ?? draftFromArticle(current.article), current.version)
      }
      draftChanged.value = true
      notice.value = "文章已撤下。"
    }
  },
)

const actionBlocked = computed(() => publish.pending.value || publish.uncertain.value || destroy.pending.value || destroy.uncertain.value)

function input(name: keyof ArticleDraft, event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement)) return
  if (name === "comments_enabled") {
    save.set(name, target instanceof HTMLInputElement && target.checked, "choice")
  } else if (name === "category_id" || name === "author_id" || name === "related_tournament_id") {
    const number = target.value ? Number(target.value) : null
    save.set(name, number, "choice")
  } else if (name === "go_live_at" || name === "expire_at") {
    save.set(name, wireDateTime(target.value, values.value[name]), "choice")
  } else if (name !== "cover_image_id") {
    save.set(name, target.value)
  }
}

async function preparePublication(): Promise<void> {
  if (!canPublish.value || actionBlocked.value || !await save.flush()) return
  publication.value = true
}
async function publishNow(): Promise<void> {
  if (!canPublish.value || actionBlocked.value || !await save.flush()) return
  if (!id.value) return
  await publish.submit({ id: id.value, base_version: save.snapshot.value.version })
}
async function destructiveNow(): Promise<void> {
  if (!destructive.value || actionBlocked.value || !await save.flush()) return
  if (!id.value) return
  await destroy.submit({ id: id.value, kind: destructive.value })
}
async function openPreview(): Promise<void> {
  if (!id.value) return
  const target = window.open("about:blank", "_blank")
  if (target) target.opener = null
  if (!await save.flush()) { target?.close(); return }
  const url = previewURL.value
  if(!url){target?.close();notice.value="预览暂时无法打开，请重新打开页面。";return}
  if (target) target.location.replace(url)
  else notice.value = "浏览器拦住了预览窗口，请允许弹窗后重试。"
}


</script>
<template>
  <div :class="article ? 'b-split' : 'b-single'">
    <form class="b-form" novalidate @submit.prevent="save.save">
      <SubmissionGuide v-if="props.detail?.guide" />
      <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
      <p v-if="notice" class="c-notice c-notice--ok" role="status">{{ notice }}</p>
      <ContentActionMessage :message="publish.message.value" :pending="publish.pending.value" :uncertain="publish.uncertain.value" @retry="publish.retry" />
      <ContentActionMessage :message="destroy.message.value" :pending="destroy.pending.value" :uncertain="destroy.uncertain.value" @retry="destroy.retry" />
      <fieldset class="b-fieldset" :disabled="!editable || actionBlocked">
        <legend class="b-section__title">内容</legend>
        <ContentField name="title" label="标题" :errors="fields.title" required>
          <template #default="field"><input :id="field.id" class="c-input" name="title" :value="values.title" maxlength="255" :aria-describedby="field.describedby" @input="input('title', $event)"></template>
        </ContentField>
        <ContentField name="category_id" label="分类" :errors="fields.category_id" required>
          <template #default="field"><select :id="field.id" class="c-input" name="category_id" :value="values.category_id ?? ''" :aria-describedby="field.describedby" @change="input('category_id', $event)"><option value="">未选分类</option><option v-for="item in categories" :key="item.id" :value="item.id">{{ item.name }}</option></select></template>
        </ContentField>
        <ContentField name="cover_image_id" label="封面" :errors="fields.cover_image_id" hint="未选封面时使用默认图片。"><ImageField name="cover_image_id" label="封面" :model-value="values.cover_image_id" :disabled="!editable || actionBlocked" @update:model-value="save.set('cover_image_id', $event, 'choice')" /></ContentField>
        <ContentField name="summary" label="摘要" :errors="fields.summary" hint="写一两句，会显示在文章列表和分享卡片上。">
          <template #default="field"><textarea :id="field.id" class="c-input" name="summary" :value="values.summary" rows="3" :aria-describedby="field.describedby" @input="input('summary', $event)" /></template>
        </ContentField>
        <ContentField name="body_md" label="正文" :errors="fields.body_md" required>
          <template #default="field"><MarkdownEditor ref="editor" :id="field.id" :model-value="values.body_md" :disabled="!editable || actionBlocked" :describedby="field.describedby" :invalid="Boolean(fields.body_md?.length)" @update:model-value="save.set('body_md', $event)" /></template>
        </ContentField>
        <ContentField name="related_tournament_id" label="关联赛事" :errors="fields.related_tournament_id" hint="选填，文章里会显示这项赛事。">
          <select id="related_tournament_id" name="related_tournament_id" class="c-input" :value="values.related_tournament_id ?? ''" @change="input('related_tournament_id', $event)"><option value="">未关联</option><option v-for="item in props.detail?.tournaments ?? []" :key="item.id" :value="item.id">{{ item.title }}</option></select>
        </ContentField>
      </fieldset>
      <fieldset v-if="props.detail && (props.detail.capabilities.edit_author || !props.detail.guide)" class="b-fieldset" :disabled="!editable || actionBlocked">
        <legend class="b-section__title">作者和评论</legend>
        <ContentField v-if="props.detail.capabilities.edit_author" name="author_id" label="作者" :errors="fields.author_id" ><select id="author_id" name="author_id" class="c-input" :value="values.author_id ?? ''" @change="input('author_id', $event)"><option value="">本人</option><option v-for="item in props.detail?.authors ?? []" :key="item.id" :value="item.id">{{ item.nickname }}</option></select></ContentField>
        <label v-if="!props.detail.guide" class="c-check"><input type="checkbox" name="comments_enabled" :checked="values.comments_enabled" @change="input('comments_enabled', $event)">开放评论</label>
      </fieldset>
      <fieldset v-if="props.detail?.capabilities.edit_schedule" class="b-fieldset" :disabled="!editable || actionBlocked">
        <legend class="b-section__title">网址和发布时间</legend>
        <ContentField name="slug" label="网址片段" :errors="fields.slug" hint="空着时按标题生成。">
          <template #default="field"><input :id="field.id" class="c-input" name="slug" :value="values.slug" maxlength="255" :aria-describedby="field.describedby" @input="input('slug', $event)"></template>
        </ContentField>
        <ContentField name="seo_title" label="SEO 标题" :errors="fields.seo_title">
          <template #default="field"><input :id="field.id" class="c-input" name="seo_title" :value="values.seo_title" maxlength="255" @input="input('seo_title', $event)"></template>
        </ContentField>
        <ContentField name="search_description" label="搜索描述" :errors="fields.search_description">
          <template #default="field"><textarea :id="field.id" class="c-input" name="search_description" :value="values.search_description" rows="3" @input="input('search_description', $event)" /></template>
        </ContentField>
        <ContentField name="go_live_at" label="定时上线" :errors="fields.go_live_at" hint="北京时间；空着就是立即发布。">
          <template #default="field"><input :id="field.id" class="c-input" name="go_live_at" type="datetime-local" :value="localDateTime(values.go_live_at)" @change="input('go_live_at', $event)"></template>
        </ContentField>
        <ContentField name="expire_at" label="定时下线" :errors="fields.expire_at" hint="北京时间；空着就不自动撤下。">
          <template #default="field"><input :id="field.id" class="c-input" name="expire_at" type="datetime-local" :value="localDateTime(values.expire_at)" @change="input('expire_at', $event)"></template>
        </ContentField>
      </fieldset>
      <div class="b-formbar">
        <button v-if="canPublish" type="button" class="c-btn c-btn--primary" :disabled="save.pending.value || actionBlocked || !publish.canStart.value" @click="preparePublication">发布</button>
        <button type="submit" class="c-btn c-btn--secondary" :disabled="!editable || actionBlocked || save.pending.value">保存草稿</button>
        <button v-if="id" type="button" class="c-btn c-btn--quiet" :disabled="save.pending.value" @click="openPreview">预览草稿</button>
        <span v-if="article?.live && (draftChanged || save.dirty.value)" class="b-formbar__note">有改动还没发布</span>
      </div>
      <ArticlePublication v-if="publication" :draft="values" :pending="publish.pending.value" @publish="publishNow" @cancel="publication = false" />
      <ConfirmContentAction v-if="destructive" :title="destructive === 'delete' ? '删除这篇文章？' : '撤下这篇文章？'" :description="destructive === 'delete' ? '删除后不能恢复。' : '撤下后变回草稿，访客看不到。'" :danger="destructive === 'delete'" :pending="destroy.pending.value" @confirm="destructiveNow" @cancel="destructive = null" />
    </form>
    <aside v-if="article || id" class="b-aside" aria-label="这篇文章">
      <section class="b-section">
        <h2 class="b-section__title">状态</h2>
        <dl class="b-kv">
          <dt>状态</dt><dd>{{ article?.live ? (draftChanged || save.dirty.value ? '已发布·有改动' : '已发布') : article?.go_live_at ? '定时上线' : '草稿' }}</dd>
          <dt>作者</dt><dd>{{ article?.author_name || permission.user.value?.nickname }}</dd>
          <template v-if="article?.first_published_at"><dt>首次发布</dt><dd>{{ formatContentTime(article.first_published_at) }}</dd></template>
          <template v-if="article?.last_published_at"><dt>最后发布</dt><dd>{{ formatContentTime(article.last_published_at) }}</dd></template>
          <template v-if="values.go_live_at"><dt>定时上线</dt><dd>{{ localDateTime(values.go_live_at).replace('T', ' ') }}</dd></template>
          <template v-if="values.expire_at"><dt>定时下线</dt><dd>{{ localDateTime(values.expire_at).replace('T', ' ') }}</dd></template>
        </dl>
        <div class="b-actions">
          <a v-if="article?.live" class="c-btn c-btn--secondary c-btn--sm" :href="`/news/${encodeURIComponent(article.slug)}/`" target="_blank" rel="noopener">看文章</a>
          <RouterLink v-if="id && props.detail?.capabilities.announce && (article?.live || article?.go_live_at)" class="c-btn c-btn--secondary c-btn--sm" :to="`/admin/announce/article/${id}/`">通知全体成员<span v-if="props.detail?.announced">（发过 {{ props.detail.announced }} 次）</span></RouterLink>
          <RouterLink v-if="id" class="c-btn c-btn--quiet c-btn--sm" :to="`/admin/articles/${id}/revisions/`">修订</RouterLink>
        </div>
        <div v-if="article && (props.detail?.capabilities.unpublish || props.detail?.capabilities.delete)" class="b-actions">
          <button v-if="props.detail?.capabilities.unpublish" type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="actionBlocked || !destroy.canStart.value" @click="destructive = 'unpublish'">撤下</button>
          <button v-if="props.detail?.capabilities.delete" type="button" class="c-btn c-btn--danger c-btn--sm" :disabled="actionBlocked || !destroy.canStart.value" @click="destructive = 'delete'">删除</button>
        </div>
      </section>
      <section v-if="props.detail?.verdict" class="b-section" data-ai-verdict><h2 class="b-section__title">AI 巡查</h2><p>AI 判断：{{ props.detail.verdict.risk }}</p><p class="b-sub">{{ props.detail.verdict.checked_at || '还未巡查' }}</p><p v-if="props.detail.verdict.reason" class="b-section__text">理由：{{ props.detail.verdict.reason }}</p><p v-if="props.detail.verdict.quote" class="b-section__text">引用原文：{{ props.detail.verdict.quote }}</p><p class="b-sub">只是参考；AI 不会改动文章。</p><RouterLink class="c-link" :to="`/admin/moderation/${props.detail.verdict.id}/`">巡查详情</RouterLink></section>
    </aside>
  </div>
</template>
