<script setup lang="ts">
import { formatContentTime } from "../../pages/content/types"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import { computed, ref } from "vue"
import { primitiveValues, readSaveReceipt } from "@sjtu-ow/shared/save-receipt"
import { useAdminApi } from "../../core/api"
import SaveStatus from "../SaveStatus.vue"
import ContentField from "./ContentField.vue"
import ContentActionMessage from "./ContentActionMessage.vue"
import DraftPublication from "./DraftPublication.vue"
import MarkdownEditor from "./MarkdownEditor.vue"
import { useContentPermissions } from "../../pages/content/permissions"
import { useContentDraft } from "../../pages/content/use-draft"
import { publishPlainPage, readPlainPage, savePlainPage, type PlainPageDetail } from "../../pages/content/pending"
const props = defineProps<{ detail: PlainPageDetail }>()
const page = ref(props.detail.page)
const api = useAdminApi()
const permission = useContentPermissions()
const editor = ref<InstanceType<typeof MarkdownEditor> | null>(null)
const draft = useContentDraft({
  initial: props.detail.draft,
  version: props.detail.version,
  unpublished: props.detail.page.has_unpublished_changes,
  available: () => permission.managePages.value,
  preview_url: props.detail.preview_url,
  previewRoute: `/admin/pages/${props.detail.page.id}/preview/`,
  transport: async (body, extras) => readSaveReceipt(
    await savePlainPage(api, props.detail.page.id, body, extras),
    props.detail.draft,
    primitiveValues(props.detail.draft),
  ),
  publish: async (version, extras) => {
    const result = await publishPlainPage(api, props.detail.page.id, version, extras)
    page.value = result.page
    return result
  },
  refresh: () => readPlainPage(api, props.detail.page.id),
})
const save = draft.save
const values = save.values
const fields = save.fields
const missing = computed(() => values.value.title.trim() ? [] : ["标题"])

function text(name: "title" | "body_md" | "seo_title" | "search_description", event: Event): void {
  const target = event.target
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) save.set(name, target.value)
}


</script>
<template>
  <div class="b-split">
    <form class="b-form" novalidate @submit.prevent="save.save">
      <SaveStatus idle-message="改了就自动存成草稿，点「发布」才上线" :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
      <p v-if="draft.notice.value" class="c-notice c-notice--info" role="status">{{ draft.notice.value }}</p>
      <ContentActionMessage :message="draft.publication.message.value" :pending="draft.publication.pending.value" :uncertain="draft.publication.uncertain.value" @retry="draft.publication.retry" />
      <fieldset class="b-fieldset" :disabled="!permission.managePages.value || draft.blocked.value">
        <ContentField name="title" label="标题" :errors="fields.title" required>
          <template #default="field"><input :id="field.id" class="c-input" name="title" :value="values.title" maxlength="255" :aria-describedby="field.describedby" @input="text('title', $event)"></template>
        </ContentField>
        <ContentField name="body" label="正文" :errors="fields.body_md">
          <template #default="field"><MarkdownEditor ref="editor" name="body" :id="field.id" :model-value="values.body_md" :disabled="!permission.managePages.value || draft.blocked.value" :invalid="Boolean(fields.body_md?.length)" :describedby="field.describedby" @update:model-value="save.set('body_md', $event)" /></template>
        </ContentField>
        <ContentField name="seo_title" label="搜索结果里的标题" hint="空着就用页面标题。" :errors="fields.seo_title">
          <template #default="field"><input :id="field.id" class="c-input" name="seo_title" :value="values.seo_title" maxlength="255" @input="text('seo_title', $event)"></template>
        </ContentField>
        <ContentField name="search_description" label="搜索描述" :errors="fields.search_description" hint="显示在搜索引擎结果中，位于标题之下的描述性文字。">
          <template #default="field"><textarea :id="field.id" class="c-input" name="search_description" :value="values.search_description" rows="3" :aria-describedby="field.describedby" @input="text('search_description', $event)" /></template>
        </ContentField>
      </fieldset>
      <div class="b-formbar">
        <button v-if="detail.can_publish" type="submit" name="publish" value="1" class="c-btn c-btn--primary" :disabled="!draft.publication.canStart.value || save.pending.value" @click.prevent="draft.prepare">发布</button>
        <button type="submit" name="save" value="1" class="c-btn c-btn--secondary" hidden :disabled="!permission.managePages.value || draft.blocked.value || save.pending.value">保存草稿</button>
        <a class="c-btn c-btn--quiet" :href="`/admin/pages/${detail.page.id}/preview/`" target="_blank" rel="noopener" @click.prevent="draft.openPreview">预览草稿</a>
      </div>
      <DraftPublication v-if="draft.confirmation.value" title="页面" :pending="draft.publication.pending.value" :missing="missing" @confirm="draft.publish" @cancel="draft.confirmation.value = false" />
    </form>
    <aside class="b-aside" aria-label="这个页面">
      <section class="b-section">
        <h2 class="b-section__title">状态</h2>
        <dl class="b-kv">
          <dt>状态</dt><dd><CStatus :label="page.live ? draft.unpublished.value || save.dirty.value ? '已发布·有改动' : '已发布' : page.expired ? '已下线' : page.approved_schedule ? '定时上线' : '草稿'" :kind="page.live ? draft.unpublished.value || save.dirty.value ? 'warn' : 'ok' : page.expired ? 'off' : page.approved_schedule ? 'info' : 'done'" /></dd>
          <dt>地址</dt><dd class="b-mono">/{{ page.slug }}/</dd><template v-if="page.last_published_at"><dt>最后发布</dt><dd>{{ formatContentTime(page.last_published_at) }}</dd></template>
        </dl>
        <div v-if="page.live" class="b-actions"><a class="c-btn c-btn--secondary c-btn--sm" :href="`/${encodeURIComponent(page.slug)}/`" target="_blank" rel="noopener">打开页面<CIcon name="external" class="size-4" /></a></div>
      </section>
    </aside>
  </div>
</template>
