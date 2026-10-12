<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { ApiError, deleteApiAdminCategoriesId, patchApiAdminCategoriesId, postApiAdminCategories } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminSave } from "../../core/use-save"
import { useAdminAction } from "../../core/use-action"
import SaveStatus from "../SaveStatus.vue"
import ContentField from "./ContentField.vue"
import ContentActionMessage from "./ContentActionMessage.vue"
import ConfirmContentAction from "./ConfirmContentAction.vue"
import { useContentPermissions } from "../../pages/content/permissions"
import { emptyCategory, readContentCurrent, type CategoryDraft } from "../../pages/content/save-values"
import type { Category } from "../../pages/content/types"

const props = defineProps<{ category: Category | null }>()
const api = useAdminApi()
const router = useRouter()
const route = useRoute()
const permission = useContentPermissions()
const id = ref(props.category?.id ?? null)
const category = ref(props.category)
const confirmation = ref(false)
const notice = ref("")
const initial: CategoryDraft = props.category ? {
  name: props.category.name,
  slug: props.category.slug,
  description: props.category.description,
  sort_order: props.category.sort_order,
  allow_submission: props.category.allow_submission,
} : emptyCategory()
const canDelete = computed(() => permission.manageCategories.value && category.value?.article_count === 0)
const save: ReturnType<typeof useAdminSave<CategoryDraft>> = useAdminSave<CategoryDraft>({
  initial,
  version: props.category?.version ?? 0,
  available: () => permission.manageCategories.value,
  readCurrent: (value) => readContentCurrent(value, initial),
  transport: async (body, key, signal) => {
    const merged = { ...save.snapshot.value.committed, ...body.changes }
    const extras = { key, signal, unauthorized: "throw" as const }
    const result = id.value
      ? await patchApiAdminCategoriesId(api, id.value, { ...merged, version: body.base_version }, extras)
      : await postApiAdminCategories(api, merged, extras)
    if (!result.category) throw new ApiError(0, "invalid_receipt", "分类保存回执无效，请重试。")
    category.value = result.category
    id.value = result.category.id
    const values: CategoryDraft = {
      name: result.category.name,
      slug: result.category.slug,
      description: result.category.description,
      sort_order: result.category.sort_order,
      allow_submission: result.category.allow_submission,
    }
    return {
      version: result.category.version,
      saved: Object.keys(body.changes),
      values,
      saved_at: result.category.updated_at,
    }
  },
})
watch(save.snapshot, (snapshot) => {
  if (id.value && route.params.id === undefined && !snapshot.dirty && !snapshot.saving && snapshot.state === "saved") {
    void router.replace(`/admin/categories/${id.value}/`)
  }
})
const values = save.values
const fields = save.fields
const deletion = useAdminAction(
  async (_: null, extras) => {
    if (!id.value || !canDelete.value) throw new ApiError(409, "in_use", "这个分类还有文章在用，不能删除。")
    return deleteApiAdminCategoriesId(api, id.value, extras)
  },
  async () => { await router.push("/admin/categories/") },
)
function input(name: "name" | "slug" | "description", event: Event): void {
  const target = event.target
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) save.set(name, target.value)
}
function order(event: Event): void {
  if (!(event.target instanceof HTMLInputElement)) return
  const value = Number(event.target.value)
  if (!Number.isSafeInteger(value)) return
  save.set("sort_order", value, "choice")
}
function submission(event: Event): void {
  if (event.target instanceof HTMLInputElement) save.set("allow_submission", event.target.checked, "choice")
}
async function saved(): Promise<void> {
  if (await save.save()) notice.value = "分类已保存。"
}
async function remove(): Promise<void> {
  if (await save.flush()) await deletion.submit(null)
}
</script>
<template>
  <div :class="id ? 'b-split' : 'b-single'">
    <form class="b-form" novalidate @submit.prevent="saved">
      <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
      <p v-if="notice" class="c-notice c-notice--ok" role="status">{{ notice }}</p>
      <ContentActionMessage :message="deletion.message.value" :pending="deletion.pending.value" :uncertain="deletion.uncertain.value" @retry="deletion.retry" />
      <fieldset class="b-fieldset" :disabled="!permission.manageCategories.value || deletion.pending.value || deletion.uncertain.value">
        <ContentField name="name" label="名称" :errors="fields.name" hint="名称或网址片段空着时，网站上不出现这个分类。">
          <template #default="field">
            <input :id="field.id" class="c-input" name="name" :value="values.name" maxlength="255" :aria-describedby="field.describedby" @input="input('name', $event)">
          </template>
        </ContentField>
        <ContentField name="slug" label="网址片段" :errors="fields.slug" hint="资讯栏目按分类筛选时地址里用的词，只用字母、数字和连字符。">
          <template #default="field">
            <input :id="field.id" class="c-input" name="slug" :value="values.slug" maxlength="255" :aria-describedby="field.describedby" @input="input('slug', $event)">
          </template>
        </ContentField>
        <ContentField name="sort_order" label="排序" required :errors="fields.sort_order" hint="数字小的排在前面。">
          <template #default="field">
            <input :id="field.id" class="c-input" name="sort_order" type="number" step="1" :value="values.sort_order" @change="order">
          </template>
        </ContentField>
        <div class="c-field"><label class="c-check"><input type="checkbox" name="allow_submission" :checked="values.allow_submission" @change="submission"><span>开放投稿</span></label><div class="c-field__help">关掉后普通成员写文章时不能选这个分类。</div></div>
      </fieldset>
      <div class="b-actions" hidden>
        <button hidden type="submit" class="c-btn c-btn--primary" :disabled="!permission.manageCategories.value || deletion.pending.value || deletion.uncertain.value || save.pending.value">保存</button>
      </div>
      <ConfirmContentAction v-if="confirmation" :title="`删除分类「${values.name}」？`" description="删除后不能恢复。" :pending="deletion.pending.value" danger @confirm="remove" @cancel="confirmation = false" />
    </form>
    <aside v-if="id" class="b-aside">
      <section class="b-section">
        <h2 class="b-section__title">这个分类</h2>
        <p v-if="category?.article_count" class="b-section__text">有 {{ category.article_count }} 篇文章在这个分类里，要删先把它们改到别的分类。</p>
        <p v-else-if="category?.article_count === 0" class="b-section__text">没有文章在用。</p>
        <p v-else class="b-section__text">文章数暂未提供，删除操作不可用。</p>
        <button v-if="canDelete" type="submit" class="c-btn c-btn--danger c-btn--sm" :disabled="!deletion.canStart.value" @click.prevent="confirmation = true">删除分类</button>
      </section>
    </aside>
  </div>
</template>
