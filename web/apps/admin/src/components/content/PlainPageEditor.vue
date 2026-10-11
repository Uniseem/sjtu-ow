<script setup lang="ts">
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
const api = useAdminApi()
const permission = useContentPermissions()
const editor = ref<InstanceType<typeof MarkdownEditor> | null>(null)
const draft = useContentDraft({
  initial: props.detail.draft,
  version: props.detail.version,
  unpublished: props.detail.page.has_unpublished_changes,
  available: () => permission.managePages.value,
  preview_url: props.detail.preview_url,
  transport: async (body, extras) => readSaveReceipt(
    await savePlainPage(api, props.detail.page.id, body, extras),
    props.detail.draft,
    primitiveValues(props.detail.draft),
  ),
  publish: (version, extras) => publishPlainPage(api, props.detail.page.id, version, extras),
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
      <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
      <p v-if="draft.notice.value" class="c-notice c-notice--info" role="status">{{ draft.notice.value }}</p>
      <ContentActionMessage :message="draft.publication.message.value" :pending="draft.publication.pending.value" :uncertain="draft.publication.uncertain.value" @retry="draft.publication.retry" />
      <fieldset class="b-fieldset" :disabled="!permission.managePages.value || draft.blocked.value">
        <ContentField name="title" label="标题" :errors="fields.title" required>
          <template #default="field"><input :id="field.id" class="c-input" name="title" :value="values.title" maxlength="255" :aria-describedby="field.describedby" @input="text('title', $event)"></template>
        </ContentField>
        <ContentField name="body_md" label="正文" :errors="fields.body_md">
          <template #default="field"><MarkdownEditor ref="editor" :id="field.id" :model-value="values.body_md" :disabled="!permission.managePages.value || draft.blocked.value" :invalid="Boolean(fields.body_md?.length)" :describedby="field.describedby" @update:model-value="save.set('body_md', $event)" /></template>
        </ContentField>
        <ContentField name="seo_title" label="SEO 标题" :errors="fields.seo_title">
          <template #default="field"><input :id="field.id" class="c-input" name="seo_title" :value="values.seo_title" maxlength="255" @input="text('seo_title', $event)"></template>
        </ContentField>
        <ContentField name="search_description" label="搜索描述" :errors="fields.search_description">
          <template #default="field"><textarea :id="field.id" class="c-input" name="search_description" :value="values.search_description" rows="3" @input="text('search_description', $event)" /></template>
        </ContentField>
      </fieldset>
      <div class="b-formbar">
        <button v-if="detail.can_publish" type="button" class="c-btn c-btn--primary" :disabled="!draft.publication.canStart.value || save.pending.value" @click="draft.prepare">发布</button>
        <button class="c-btn c-btn--secondary" :disabled="!permission.managePages.value || draft.blocked.value || save.pending.value">保存草稿</button>
        <button type="button" class="c-btn c-btn--quiet" :disabled="save.pending.value" @click="draft.openPreview">预览草稿</button>
      </div>
      <DraftPublication v-if="draft.confirmation.value" title="页面" :pending="draft.publication.pending.value" :missing="missing" @confirm="draft.publish" @cancel="draft.confirmation.value = false" />
    </form>
    <aside class="b-aside" aria-label="这个页面">
      <section class="b-section">
        <h2 class="b-section__title">状态</h2>
        <dl class="b-kv">
          <dt>状态</dt><dd>{{ draft.unpublished.value || save.dirty.value ? '有改动还没发布' : detail.page.live ? '已发布' : '草稿' }}</dd>
          <dt>地址</dt><dd class="b-mono">/{{ detail.page.slug }}/</dd>
        </dl>
        <p class="b-section__text">「有改动」是说草稿里有还没发布的改动；网站上还是上次发布的样子。</p>
        <a v-if="detail.page.live" class="c-btn c-btn--secondary c-btn--sm" :href="`/${encodeURIComponent(detail.page.slug)}/`" target="_blank" rel="noopener">打开页面</a>
      </section>
    </aside>
  </div>
</template>
