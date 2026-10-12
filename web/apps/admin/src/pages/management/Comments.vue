<script setup lang="ts">
import { ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiAdminComments, postApiCommentsIdHide, postApiCommentsIdPin } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ActionState from "../../components/management/ActionState.vue"
import ManagementPager from "../../components/management/ManagementPager.vue"
import { useResource } from "./use-resource"
import { positive, text, date } from "./format"
const route = useRoute()
const router = useRouter()
const api = useAdminApi()
const search = ref(text(route.query.q))
const shown = ref(text(route.query.show) || (route.query.hidden === '1' ? 'hidden' : route.query.pinned === '1' ? 'pinned' : ''))
const resource = useResource(() => route.fullPath, signal => getApiAdminComments(api, { q: text(route.query.q), hidden: route.query.show === 'hidden' || route.query.hidden === '1' ? true : undefined, pinned: route.query.show === 'pinned' || route.query.pinned === '1' ? true : undefined, page: positive(route.query.page), page_size: 50 }, { signal }))
const action = useAdminAction<{ kind: 'hide' | 'pin'; id: number; article: number; enabled: boolean }, { result: string }>((body, extras) => body.kind === 'hide' ? postApiCommentsIdHide(api, body.id, { hidden: body.enabled }, extras) : postApiCommentsIdPin(api, body.id, { pinned: body.enabled, article_id: body.article }, extras), () => resource.refresh())
function filter() { void router.push({ path: route.path, query: { q: search.value || undefined, show: shown.value || undefined } }) }
</script>
<template>
  <AdminPage title="评论" section="审核">
    <form class="b-filters" role="search" @submit.prevent="filter">
      <input v-model="search" class="c-input" type="search" name="q" maxlength="50" placeholder="搜评论内容" aria-label="搜评论" />
      <select v-model="shown" name="show" class="c-input" aria-label="哪些评论" @change="filter"><option value="">全部评论</option><option value="hidden">只看隐藏的</option><option value="pinned">只看置顶的</option></select>
          <button class="c-btn c-btn--secondary c-btn--sm">筛选</button>
        </form>
        <p class="b-section__text">评论只能隐藏和置顶，不能删除或改字。每篇文章只能置顶一条顶层评论。</p>
        <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
        <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
        <table v-if="resource.data.value?.items.length" class="c-table c-table--stack">
          <thead>
            <tr>
              <th scope="col">评论</th>
              <th scope="col">作者</th>
              <th scope="col">文章</th>
              <th scope="col">时间</th>
              <th>状态</th><th><span class="sr-only">操作</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="comment in resource.data.value.items" :key="comment.id" :data-comment-row="comment.id">
              <td>{{ comment.content.length > 200 ? comment.content.slice(0, 199) + '…' : comment.content }}</td>
              <td data-label="作者">{{ comment.author_name }}</td><td data-label="文章">{{ comment.article_title }}</td><td data-label="时间">{{ date(comment.created_at) }}</td>
              <td data-label="状态">{{ comment.is_hidden ? '已隐藏' : comment.is_pinned ? '置顶' : '—' }}</td>
              <td class="b-rowacts">
                <button type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="!action.canStart.value || comment.is_deleted" @click="action.submit({ kind: 'hide', id: comment.id, article: comment.article_id, enabled: !comment.is_hidden })">{{ comment.is_hidden ? '恢复' : '隐藏' }}</button>
                <button v-if="!comment.is_hidden && (comment.is_pinned || comment.is_top_level)" type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="!action.canStart.value || comment.is_deleted" @click="action.submit({ kind: 'pin', id: comment.id, article: comment.article_id, enabled: !comment.is_pinned })">{{ comment.is_pinned ? '取消置顶' : '置顶' }}</button>
              </td>
            </tr>
          </tbody>
        </table>
        <CEmpty v-else-if="!resource.pending.value && !resource.message.value" title="没有评论" message="换个筛选条件试试。" />
        <ManagementPager v-if="resource.data.value" :page="resource.data.value.page" :size="resource.data.value.page_size" :total="resource.data.value.total" />
      </AdminPage>
</template>
