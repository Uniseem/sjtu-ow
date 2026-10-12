<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { deleteApiAdminCategoriesId, getApiAdminCategories } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import ContentActionMessage from "../../components/content/ContentActionMessage.vue"
import ConfirmContentAction from "../../components/content/ConfirmContentAction.vue"
import { useContentResource } from "./use-resource"
import { useContentPermissions } from "./permissions"
import type { Category } from "./types"

const api = useAdminApi()
const permission = useContentPermissions()
const confirmation = ref<Category | null>(null)
const notice = ref("")
const resource = useContentResource((signal) => getApiAdminCategories(api, { signal }))
const rows = computed(() => (resource.data.value?.items ?? [])
  .filter((item): item is Category => item !== null)
  .sort((left, right) => left.sort_order - right.sort_order || left.name.localeCompare(right.name, "zh-CN") || left.id - right.id))
const action = useAdminAction(
  (id: number, extras) => deleteApiAdminCategoriesId(api, id, extras),
  async () => {
    confirmation.value = null
    notice.value = "分类已删除。"
    await resource.load()
  },
)
function remove(): void {
  if (!confirmation.value || !permission.manageCategories.value || confirmation.value.article_count !== 0) return
  void action.submit(confirmation.value.id)
}
onMounted(() => { void resource.load() })
</script>
<template>
  <AdminPage title="分类" section="content">
    <template #actions>
      <RouterLink v-if="permission.manageCategories.value" class="c-btn c-btn--primary c-btn--sm" to="/admin/categories/new/">新建分类</RouterLink>
    </template>
    <ContentLoad
      :pending="resource.pending.value"
      :message="resource.message.value"
      :status="resource.status.value"
      @retry="resource.load"
    />
    <p v-if="notice" class="c-notice c-notice--ok" role="status">{{ notice }}</p>
    <ContentActionMessage
      :message="action.message.value"
      :pending="action.pending.value"
      :uncertain="action.uncertain.value"
      @retry="action.retry"
    />
    <ConfirmContentAction
      v-if="confirmation"
      :title="`删除分类「${confirmation.name}」？`"
      description="没有文章在用的分类才可以删除。"
      :pending="action.pending.value"
      danger
      @confirm="remove"
      @cancel="confirmation = null"
    />
    <table v-if="rows.length" class="c-table c-table--stack">
      <thead>
        <tr>
          <th>名称</th>
          <th>网址片段</th>
          <th class="is-num">排序</th>
          <th>开放投稿</th>
          <th class="is-num">文章</th>
          <th><span class="sr-only">操作</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in rows" :key="item.id" :data-category-row="item.id">
          <td>
            <RouterLink class="b-title" :to="`/admin/categories/${item.id}/`">{{ item.name || '（未命名分类）' }}</RouterLink>
            <span v-if="!item.name || !item.slug" class="b-sub">名称或网址片段空着，网站上不显示</span>
          </td>
          <td data-label="网址片段"><span class="b-mono">{{ item.slug }}</span></td>
          <td data-label="排序" class="is-num">{{ item.sort_order }}</td>
          <td data-label="开放投稿">{{ item.allow_submission ? '是' : '否' }}</td>
          <td data-label="文章" class="is-num">{{ item.article_count ?? '—' }}</td>
          <td>
            <div class="b-rowacts">
              <RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="`/admin/categories/${item.id}/`">编辑</RouterLink>
              <button
                v-if="permission.manageCategories.value && item.article_count === 0"
                type="submit"
                class="c-btn c-btn--quiet c-btn--sm"
                :disabled="!action.canStart.value"
                data-delete-category
                @click.prevent="confirmation = item"
              >删除</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <section v-else-if="resource.data.value" class="c-empty">
      <h2 class="c-empty__title">还没有分类</h2>
      <p>写文章要先选分类。</p>
      <RouterLink v-if="permission.manageCategories.value" class="c-btn c-btn--primary" to="/admin/categories/new/">新建分类</RouterLink>
    </section>
  </AdminPage>
</template>
