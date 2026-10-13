<script setup lang="ts">
import { formatContentTime } from "../../pages/content/types"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import { ref } from "vue"
import { primitiveValues, readSaveReceipt } from "@sjtu-ow/shared/save-receipt"
import { useAdminApi } from "../../core/api"
import SaveStatus from "../SaveStatus.vue"
import ContentField from "./ContentField.vue"
import ContentActionMessage from "./ContentActionMessage.vue"
import DraftPublication from "./DraftPublication.vue"
import MarkdownEditor from "./MarkdownEditor.vue"
import { useContentDraft } from "../../pages/content/use-draft"
import { useContentPermissions } from "../../pages/content/permissions"
import { readNewsDraft, saveNewsDraft, publishNewsDraft, type NewsDraftProjection } from "../../pages/content/pending"

const props = defineProps<{ detail: NewsDraftProjection }>()
const publicationState = ref({ live: props.detail.live, last_published_at: props.detail.last_published_at })
const api = useAdminApi()
const permission = useContentPermissions()
const editor = ref<InstanceType<typeof MarkdownEditor> | null>(null)
const draft = useContentDraft({
  initial: props.detail.draft,
  version: props.detail.version,
  unpublished: props.detail.has_unpublished_changes,
  available: () => permission.managePages.value,
  preview_url: props.detail.preview_url,
  transport: async (body, extras) => readSaveReceipt(await saveNewsDraft(api, body, extras), props.detail.draft, primitiveValues(props.detail.draft)),
  publish: async (version, extras) => {
    const result = await publishNewsDraft(api, version, extras)
    publicationState.value = { live: result.live, last_published_at: result.last_published_at }
    return result
  },
  refresh: () => readNewsDraft(api),
})
const save = draft.save
</script>
<template>
  <div class="b-split">
    <form class="b-form" novalidate @submit.prevent="save.save">
      <SaveStatus idle-message="改了就自动存成草稿，点「发布」才上线" :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
      <p v-if="draft.notice.value" class="c-notice c-notice--info" role="status">{{ draft.notice.value }}</p>
      <ContentActionMessage :message="draft.publication.message.value" :pending="draft.publication.pending.value" :uncertain="draft.publication.uncertain.value" @retry="draft.publication.retry" />
      <fieldset class="b-fieldset" :disabled="!permission.managePages.value || draft.blocked.value">
        <ContentField name="intro" label="栏目介绍" hint="显示在资讯栏目顶部。点「发布」后生效。" :errors="save.fields.value.intro_md">
          <template #default="field"><MarkdownEditor ref="editor" name="intro" :id="field.id" label="栏目介绍" :model-value="save.values.value.intro_md" :describedby="field.describedby" :invalid="Boolean(save.fields.value.intro_md?.length)" :disabled="!permission.managePages.value || draft.blocked.value" @update:model-value="save.set('intro_md', $event)" /></template>
        </ContentField>
      </fieldset>
      <div class="b-formbar">
        <button v-if="detail.can_publish" type="submit" name="publish" value="1" class="c-btn c-btn--primary" :disabled="!draft.publication.canStart.value || save.pending.value" @click.prevent="draft.prepare">发布</button>
        <button type="submit" name="save" value="1" class="c-btn c-btn--secondary" hidden :disabled="!permission.managePages.value || draft.blocked.value || save.pending.value">保存草稿</button>
      </div>
      <DraftPublication v-if="draft.confirmation.value" title="栏目介绍" :pending="draft.publication.pending.value" @confirm="draft.publish" @cancel="draft.confirmation.value = false" />
    </form>
    <aside class="b-aside" aria-label="状态">
      <section class="b-section"><h2 class="b-section__title">状态</h2><dl class="b-kv"><dt>状态</dt><dd data-draft-status><CStatus :label="publicationState.live ? draft.unpublished.value || save.dirty.value ? '已发布·有改动' : '已发布' : '草稿'" :kind="publicationState.live ? draft.unpublished.value || save.dirty.value ? 'warn' : 'ok' : 'done'" /></dd><template v-if="publicationState.last_published_at"><dt>最后发布</dt><dd>{{ formatContentTime(publicationState.last_published_at) }}</dd></template></dl><p class="b-section__text">「有改动」是说草稿里有还没发布的改动；网站上还是上次发布的样子。</p></section>
    </aside>
  </div>
</template>
