<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { ApiError } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import ContentField from "../../components/content/ContentField.vue"
import CollectionName from "../../components/content/CollectionName.vue"
import ContentActionMessage from "../../components/content/ContentActionMessage.vue"
import ConfirmContentAction from "../../components/content/ConfirmContentAction.vue"
import { useContentResource } from "./use-resource"
import { collectionRows, hasCollectionChildren } from "./collection-tree"
import { createCollection, deleteCollection, readCollectionTree, type CollectionCreateInput, type CollectionNode } from "./pending"
import { useContentPermissions } from "./permissions"

const api = useAdminApi()
const permission = useContentPermissions()
const resource = useContentResource((signal) => readCollectionTree(api, { signal }))
const rows = computed(() => collectionRows(resource.data.value?.collections ?? []))
const parents = computed(() => rows.value.filter((row) => row.node.can_add))
const parent = ref<number | null>(null)
const name = ref("")
const notice = ref("")
const confirmation = ref<CollectionNode | null>(null)
const creation = useAdminAction(
  (body: CollectionCreateInput, extras) => createCollection(api, body, extras),
  async (result) => {
    if (!result.collection) throw new ApiError(0, "invalid_receipt", "集合创建回执无效，请重试。")
    name.value = ""
    notice.value = "集合已建好。"
    await resource.load()
  },
)
const deletion = useAdminAction(
  (id: number, extras) => deleteCollection(api, id, extras),
  async () => {
    confirmation.value = null
    notice.value = "集合已删除。"
    await resource.load()
  },
)
function canDelete(node: CollectionNode): boolean {
  return node.can_delete && node.parent_id !== null && node.image_count === 0
    && !hasCollectionChildren(node.id, resource.data.value?.collections ?? [])
}
function create(): void {
  if (!parent.value || !permission.superuser.value || !creation.canStart.value) return
  void creation.submit({ name: name.value, parent_id: parent.value })
}
function remove(): void {
  if (!confirmation.value || !canDelete(confirmation.value)) return
  void deletion.submit(confirmation.value.id)
}
function renamed(id: number, version: number, value: string): void {
  if (!resource.data.value) return
  resource.data.value = {
    collections: resource.data.value.collections.map((node) => node.id === id ? { ...node, name: value, version } : node),
  }
}
onMounted(async () => {
  await resource.load()
  parent.value = parents.value[0]?.node.id ?? null
})
</script>
<template>
  <AdminPage title="集合" document-title="图片集合" section="content" back-href="/admin/images/">
    <ContentLoad :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.load" />
    <p v-if="notice" class="c-notice c-notice--ok" role="status">{{ notice }}</p>
    <ContentActionMessage :message="creation.message.value" :pending="creation.pending.value" :uncertain="creation.uncertain.value" @retry="creation.retry" />
    <ContentActionMessage :message="deletion.message.value" :pending="deletion.pending.value" :uncertain="deletion.uncertain.value" @retry="deletion.retry" />
    <ConfirmContentAction v-if="confirmation" :title="`删除集合「${confirmation.name}」？`" description="集合里没有图片和子集合时才能删除。" :pending="deletion.pending.value" danger @confirm="remove" @cancel="confirmation = null" />
    <table v-if="resource.data.value" class="c-table c-table--stack">
      <thead><tr><th>集合（名称改了就存）</th><th class="is-num">图片</th><th><span class="sr-only">操作</span></th></tr></thead>
      <tbody>
        <tr v-for="row in rows" :key="row.node.id">
          <td>
            <CollectionName v-if="row.node.can_change && row.node.parent_id !== null" :node="row.node" :path="row.path" :indent="'　'.repeat(Math.max(0, row.depth - 1))" @saved="(version, name) => renamed(row.node.id, version, name)" />
            <span v-else>{{ row.node.key === 'root' ? '（根）' : row.node.name }}</span>
            <span v-if="row.orphaned" class="b-sub">集合关系异常，请联系管理员。</span>
          </td>
          <td data-label="图片" class="is-num">{{ row.node.image_count }}</td>
          <td>
            <div class="b-rowacts">
              <button v-if="canDelete(row.node)" type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="!deletion.canStart.value" @click="confirmation = row.node">删除</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <form class="b-form" novalidate @submit.prevent="create">
      <fieldset class="b-fieldset" :disabled="!permission.superuser.value || !creation.canStart.value">
        <h2 class="b-section__title">新建集合</h2>
        <p class="b-section__text">「默认封面」「默认头像」可以分子文件夹：把新集合放在它们下面，里面的图也算。</p>
        <ContentField name="name" label="名称" required :errors="creation.fields.value.name">
          <input id="name" v-model="name" class="c-input" name="name" maxlength="255" required>
        </ContentField>
        <ContentField name="parent" label="放在" required :errors="creation.fields.value.parent_id">
          <select id="parent" v-model="parent" class="c-input" name="parent"><option v-for="row in parents" :key="row.node.id" :value="row.node.id">{{ row.node.parent_id === null ? '（根）' : '　'.repeat(Math.max(0, row.depth - 1)) + row.node.name }}</option></select>
        </ContentField>
      </fieldset>
      <div class="b-actions"><button class="c-btn c-btn--primary" :disabled="!parent || !permission.superuser.value || !creation.canStart.value">建好</button></div>
    </form>
  </AdminPage>
</template>
