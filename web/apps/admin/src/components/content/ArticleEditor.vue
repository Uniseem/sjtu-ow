<script setup lang="ts">
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
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
import { articleStatus, articleStatuses, articleStatusKinds, draftFromArticle, emptyArticle, localDateTime, wireDateTime, type Article, type ArticleDraft, type Category } from "../../pages/content/types"

const props = defineProps<{ detail: ArticleEditorProjection | null; categories: Pick<Category, "id" | "name" | "allow_submission">[] }>()
const emit = defineEmits<{ created: [id: number] }>()
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
const previewURL = computed(() => id.value ? `/admin/articles/${id.value}/preview/` : null)
const editable = computed(() => props.detail?.capabilities.edit ?? (!article.value || permission.canEdit(article.value)))
const canPublish = computed(() => props.detail?.capabilities.publish ?? (article.value ? permission.canPublish(article.value)
  : Boolean(permission.user.value?.superuser || permission.user.value?.caps.includes("articles.publish_own") || permission.everyArticle.value)))
const categories = computed(() => props.categories)
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
let assigningCreatedRoute = false
watch(save.snapshot, (snapshot) => {
  if (id.value && !assigningCreatedRoute && route.params.id === undefined && !snapshot.dirty && !snapshot.saving && snapshot.state === "saved") {
    assigningCreatedRoute = true
    emit("created", id.value)
    void router.replace(`/admin/articles/${id.value}/`).catch(() => {
      notice.value = "草稿已保存，网址暂时没有更新，请重试。"
    }).finally(() => { assigningCreatedRoute = false })
  }
})
watch(() => props.detail?.article, (current) => {
  if (current && current.id === id.value) article.value = current
})
const values = save.values
const fields = save.fields

const publish = useAdminAction(
  (body: { id: number; base_version: number }, extras) => postApiArticlesIdPublish(api, body.id, { base_version: body.base_version }, extras),
  async (result) => {
    article.value = result.article
    draftChanged.value = false
    publication.value = false
    notice.value = result.article?.approved_schedule ? "已安排上线。" : "文章已发布。"
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
      <SaveStatus idle-message="改了就自动存成草稿，点「发布」才上线" :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
      <SubmissionGuide v-if="props.detail?.guide" />
      <p v-if="notice" class="c-notice c-notice--ok" role="status">{{ notice }}</p>
      <ContentActionMessage :message="publish.message.value" :pending="publish.pending.value" :uncertain="publish.uncertain.value" @retry="publish.retry" />
      <ContentActionMessage :message="destroy.message.value" :pending="destroy.pending.value" :uncertain="destroy.uncertain.value" @retry="destroy.retry" />
      <fieldset class="b-fieldset" :disabled="!editable || actionBlocked">
        <legend class="b-fieldset__legend">文章</legend>
        <ContentField name="title" label="标题" :errors="fields.title" required>
          <template #default="field"><input :id="field.id" class="c-input" name="title" :value="values.title" maxlength="255" :aria-describedby="field.describedby" @input="input('title', $event)"></template>
        </ContentField>
        <ContentField name="category_id" label="分类" :errors="fields.category_id" required>
          <template #default="field"><select :id="field.id" class="c-input" name="category" :value="values.category_id ?? ''" :aria-describedby="field.describedby" @change="input('category_id', $event)"><option value="">选一个分类</option><option v-for="item in categories" :key="item.id" :value="item.id">{{ item.name }}</option></select></template>
        </ContentField>
        <ContentField name="cover_image_id" label="封面" :errors="fields.cover_image_id" hint="空着就用默认封面图库里的一张。"><ImageField name="cover_image_id" label="封面" :model-value="values.cover_image_id" :disabled="!editable || actionBlocked" @update:model-value="save.set('cover_image_id', $event, 'choice')" /></ContentField>
        <ContentField name="summary" label="摘要" :errors="fields.summary">
          <template #default="field"><input :id="field.id" class="c-input" name="summary" :value="values.summary" maxlength="255" :aria-describedby="field.describedby" @input="input('summary', $event)"></template>
        </ContentField>
        <ContentField name="body_md" label="正文" :errors="fields.body_md">
          <template #default="field"><MarkdownEditor ref="editor" :id="field.id" :model-value="values.body_md" :disabled="!editable || actionBlocked" :describedby="field.describedby" :invalid="Boolean(fields.body_md?.length)" @update:model-value="save.set('body_md', $event)" /></template>
        </ContentField>
        <ContentField name="related_tournament_id" label="关联赛事" :errors="fields.related_tournament_id" hint="选填。关联后这篇文章会显示在赛事页面上。">
          <template #default="field"><select :id="field.id" name="tournament" class="c-input" :value="values.related_tournament_id ?? ''" :aria-describedby="field.describedby" @change="input('related_tournament_id', $event)"><option value="">不关联赛事</option><option v-for="item in props.detail?.tournaments ?? []" :key="item.id" :value="item.id">{{ item.title }}</option></select></template>
        </ContentField>
      </fieldset>
      <fieldset v-if="props.detail && (props.detail.capabilities.edit_author || props.detail.capabilities.edit_comments)" class="b-fieldset" :disabled="!editable || actionBlocked">
        <legend class="b-fieldset__legend">作者和评论</legend>
        <ContentField v-if="props.detail.capabilities.edit_author" name="author_id" label="作者" :errors="fields.author_id" hint="空着就是写这篇的人。"><select id="author_id" name="author" class="c-input" :value="values.author_id ?? ''" aria-describedby="author_id-hint" @change="input('author_id', $event)"><option value="">---------</option><option v-for="item in props.detail?.authors ?? []" :key="item.id" :value="item.id">{{ item.label }}</option></select></ContentField>
        <div v-if="props.detail.capabilities.edit_comments" class="c-field" :class="{ 'is-invalid': fields.comments_enabled?.length }">
          <label class="c-check" for="comments_enabled"><input id="comments_enabled" type="checkbox" name="comments_enabled" :checked="values.comments_enabled" :aria-describedby="fields.comments_enabled?.length ? 'comments_enabled-error' : 'comments_enabled-hint'" @change="input('comments_enabled', $event)"><span>开放评论</span></label>
          <div id="comments_enabled-hint" class="c-field__help">关闭后已有评论仍显示，只是不能再发。</div>
          <ul v-if="fields.comments_enabled?.length" id="comments_enabled-error" class="c-field__error" role="alert"><li v-for="message in fields.comments_enabled" :key="message">{{ message }}</li></ul>
        </div>
      </fieldset>
      <fieldset v-if="props.detail?.capabilities.edit_schedule" class="b-fieldset" :disabled="!editable || actionBlocked">
        <legend class="b-fieldset__legend">网址和发布时间</legend>
        <ContentField name="slug" label="网址片段" :errors="fields.slug" hint="文章地址的最后一段。空着就按标题生成。">
          <template #default="field"><input :id="field.id" class="c-input" name="slug" :value="values.slug" maxlength="255" :aria-describedby="field.describedby" @input="input('slug', $event)"></template>
        </ContentField>
        <ContentField name="seo_title" label="搜索结果里的标题" :errors="fields.seo_title" hint="空着就用文章标题。">
          <template #default="field"><input :id="field.id" class="c-input" name="seo_title" :value="values.seo_title" maxlength="255" @input="input('seo_title', $event)"></template>
        </ContentField>
        <ContentField name="search_description" label="搜索描述" :errors="fields.search_description" hint="空着就用摘要。">
          <template #default="field"><textarea :id="field.id" class="c-input" name="search_description" :value="values.search_description" rows="3" @input="input('search_description', $event)" /></template>
        </ContentField>
        <ContentField name="go_live_at" label="定时上线" :errors="fields.go_live_at" hint="到这个时间才上线。点「发布」后生效；空着就是马上上线。">
          <template #default="field"><input :id="field.id" class="c-input" name="go_live_at" type="datetime-local" :value="localDateTime(values.go_live_at)" @change="input('go_live_at', $event)"></template>
        </ContentField>
        <ContentField name="expire_at" label="定时下线" :errors="fields.expire_at" hint="到这个时间自动下线。">
          <template #default="field"><input :id="field.id" class="c-input" name="expire_at" type="datetime-local" :value="localDateTime(values.expire_at)" @change="input('expire_at', $event)"></template>
        </ContentField>
      </fieldset>
      <div class="b-formbar">
        <button v-if="canPublish" type="submit" name="publish" value="1" class="c-btn c-btn--primary" :disabled="save.pending.value || actionBlocked || !publish.canStart.value" @click.prevent="preparePublication">发布</button>
        <button type="submit" name="save" value="1" class="c-btn c-btn--secondary" hidden :disabled="!editable || actionBlocked || save.pending.value">保存草稿</button>
        <a v-if="id" class="c-btn c-btn--quiet" :href="previewURL || undefined" target="_blank" rel="noopener" @click.prevent="openPreview">预览草稿</a>
        <span v-if="article?.live && (draftChanged || save.dirty.value)" class="b-formbar__note">有改动还没发布</span>
      </div>
      <ArticlePublication v-if="publication" :draft="values" :pending="publish.pending.value" @publish="publishNow" @cancel="publication = false" />
      <ConfirmContentAction v-if="destructive" :title="destructive === 'delete' ? '删除这篇文章？' : '撤下这篇文章？'" :description="destructive === 'delete' ? '删除后不能恢复。' : '撤下后变回草稿，访客看不到。'" :danger="destructive === 'delete'" :pending="destroy.pending.value" @confirm="destructiveNow" @cancel="destructive = null" />
    </form>
    <aside v-if="article || id" class="b-aside" aria-label="这篇文章">
      <section class="b-section">
        <h2 class="b-section__title">状态</h2>
        <dl class="b-kv">
          <dt>状态</dt><dd><CStatus :label="article?.live && (draftChanged || save.dirty.value) ? '已发布·有改动' : article ? articleStatuses[articleStatus(article)] : '草稿'" :kind="article?.live && (draftChanged || save.dirty.value) ? 'warn' : article ? articleStatusKinds[articleStatus(article)] : 'done'" /></dd>
          <dt>作者</dt><dd>{{ article?.author_name || permission.user.value?.nickname }}</dd>
          <template v-if="article?.first_published_at"><dt>首次发布</dt><dd>{{ formatContentTime(article.first_published_at) }}</dd></template>
          <template v-if="article?.last_published_at"><dt>最后发布</dt><dd>{{ formatContentTime(article.last_published_at) }}</dd></template>
          <template v-if="article?.approved_schedule && article.go_live_at"><dt>定时上线</dt><dd>{{ formatContentTime(article.go_live_at) }}</dd></template>
          <template v-if="values.expire_at"><dt>定时下线</dt><dd>{{ localDateTime(values.expire_at).replace('T', ' ') }}</dd></template>
        </dl>
        <div class="b-actions">
          <a v-if="article?.live" class="c-btn c-btn--secondary c-btn--sm" :href="`/news/${encodeURIComponent(article.slug)}/`" target="_blank" rel="noopener">看文章<CIcon name="external" class="size-4" /></a>
          <RouterLink v-if="id && article?.can_announce" class="c-btn c-btn--secondary c-btn--sm" :to="`/admin/announce/article/${id}/`">{{ article?.live ? '通知全体成员' : '上线时通知全体成员' }}<span v-if="article?.announced">（发过 {{ article.announced }} 次）</span></RouterLink>
          <RouterLink v-if="id" class="c-btn c-btn--quiet c-btn--sm" :to="`/admin/articles/${id}/revisions/`">修订</RouterLink>
        </div>
        <div v-if="article && (props.detail?.capabilities.unpublish || props.detail?.capabilities.delete)" class="b-actions">
          <form v-if="props.detail?.capabilities.unpublish && article.live" @submit.prevent="destructive = 'unpublish'"><button type="submit" class="c-btn c-btn--secondary c-btn--sm" :disabled="actionBlocked || !destroy.canStart.value">撤下</button></form>
          <form v-if="props.detail?.capabilities.delete" @submit.prevent="destructive = 'delete'"><button type="submit" class="c-btn c-btn--danger c-btn--sm" :disabled="actionBlocked || !destroy.canStart.value">删除</button></form>
        </div>
      </section>
      <section v-if="props.detail?.verdict" class="b-section" data-ai-verdict><h2 class="b-section__title">AI 巡查</h2><p>AI 判断：{{ props.detail.verdict.risk }}</p><p class="b-sub">{{ props.detail.verdict.checked_at || '还未巡查' }}</p><p v-if="props.detail.verdict.reason" class="b-section__text">理由：{{ props.detail.verdict.reason }}</p><p v-if="props.detail.verdict.quote" class="b-section__text">引用原文：{{ props.detail.verdict.quote }}</p><p class="b-sub">只是参考；AI 不会改动文章。</p><RouterLink class="c-link" :to="`/admin/moderation/${props.detail.verdict.id}/`">巡查详情</RouterLink></section>
    </aside>
  </div>
</template>
