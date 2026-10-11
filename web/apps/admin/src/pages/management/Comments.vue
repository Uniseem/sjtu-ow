<script setup lang="ts">
import { ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiAdminComments, postApiCommentsIdHide, postApiCommentsIdPin } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
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
const hidden = ref(route.query.hidden === '1')
const pinned = ref(route.query.pinned === '1')
const resource = useResource(() => route.fullPath, signal => getApiAdminComments(api, { q: text(route.query.q), hidden: route.query.hidden === '1' ? true : undefined, pinned: route.query.pinned === '1' ? true : undefined, page: positive(route.query.page), page_size: 50 }, { signal }))
const action = useAdminAction<{ kind: 'hide' | 'pin'; id: number; article: number; enabled: boolean }, { result: string }>((body, extras) => body.kind === 'hide' ? postApiCommentsIdHide(api, body.id, { hidden: body.enabled }, extras) : postApiCommentsIdPin(api, body.id, { pinned: body.enabled, article_id: body.article }, extras), () => resource.refresh())
function filter() { void router.push({ path: route.path, query: { q: search.value || undefined, hidden: hidden.value ? '1' : undefined, pinned: pinned.value ? '1' : undefined } }) }
</script>
<template>
  <AdminPage title="评论" section="审核">
    <form class="b-filters" role="search" @submit.prevent="filter">
      <input v-model="search" class="c-input" type="search" placeholder="搜正文" aria-label="搜正文" />
      <label class="c-check">
        <input v-model="hidden" type="checkbox" />只看隐藏的</label>
        <label class="c-check">
          <input v-model="pinned" type="checkbox" />只看置顶的</label>
          <button class="c-btn c-btn--secondary c-btn--sm">筛选</button>
        </form>
        <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
        <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" :empty="!resource.data.value?.items.length" empty-text="没有符合条件的评论。" @retry="resource.refresh" />
        <table v-if="resource.data.value?.items.length" class="c-table">
          <thead>
            <tr>
              <th scope="col">评论</th>
              <th scope="col">作者</th>
              <th scope="col">文章</th>
              <th scope="col">时间</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="comment in resource.data.value.items" :key="comment.id">
              <td>{{ comment.content.slice(0, 200) }}<span v-if="comment.is_hidden" class="c-tag">已隐藏</span>
                <span v-if="comment.is_pinned" class="c-tag">置顶</span>
              </td>
              <td>
                <a class="c-link" :href="`/members/${comment.author_id}/`">{{ comment.author_name }}</a>
              </td>
              <td>
                <a class="c-link" :href="`/news/${encodeURIComponent(comment.article_slug)}/#comment-${comment.id}`">{{ comment.article_title }}</a>
              </td>
              <td>{{ date(comment.created_at) }}</td>
              <td class="b-rowacts">
                <button type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="!action.canStart.value || comment.is_deleted" @click="action.submit({ kind: 'hide', id: comment.id, article: comment.article_id, enabled: !comment.is_hidden })">{{ comment.is_hidden ? '恢复' : '隐藏' }}</button>
                <button type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="!action.canStart.value || comment.is_deleted" @click="action.submit({ kind: 'pin', id: comment.id, article: comment.article_id, enabled: !comment.is_pinned })">{{ comment.is_pinned ? '取消置顶' : '置顶' }}</button>
              </td>
            </tr>
          </tbody>
        </table>
        <ManagementPager v-if="resource.data.value" :page="resource.data.value.page" :size="resource.data.value.page_size" :total="resource.data.value.total" />
      </AdminPage>
</template>
