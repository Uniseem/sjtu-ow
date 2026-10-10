<script setup lang="ts">
import { computed } from "vue"
import CCommentComposer from "./CCommentComposer.vue"
import CCommentItem from "./CCommentItem.vue"
import CIcon from "./CIcon.vue"
import type { CommentView } from "./types"

// comments/templates/comments/section.html (design 5.6, 13.13.3). Rendered
// read-only for visitors (no forms) and interactive for a signed-in member,
// exactly as the old section did; the actions go to the page, which calls the
// comments API and repaints the whole section — the same semantics the old
// hx-target="#slot-article-comments" outerHTML swaps had.
const props = defineProps<{
  commentsEnabled: boolean
  thread: { total: number; page: number; pageSize: number; comments: (CommentView | null)[] }
  sort: string
  interactive: boolean
  canPost: boolean
  postProblems: string[]
  canModerate: boolean
  viewerId?: number | null
  pageUrl: string
  loginUrl: string
}>()
const emit = defineEmits<{
  more: [page: number]
  create: [payload: { content: string }]
  reply: [payload: { parentId: number; content: string }]
  edit: [comment: { id: number; content: string }]
  remove: [id: number]
  hide: [change: { id: number; hidden: boolean }]
  pin: [change: { id: number; pinned: boolean }]
}>()

// The old thread's has_next/next_number: PAGE_SIZE top-level comments a page
// (comments/services.py), so the counts Go sends answer it.
const hasMore = computed(() => props.thread.page * props.thread.pageSize < props.thread.total)
const nextPage = computed(() => props.thread.page + 1)
</script>
<template>
  <section id="slot-article-comments" data-slot="article-comments" class="c-comments">
    <div class="c-comments__head">
      <h2 id="comments">{{ thread.total ? `${thread.total} 条评论` : "评论" }}</h2>
      <nav v-if="thread.total > 1" class="c-comments__sort" aria-label="评论排序">
        <a :href="`${pageUrl}?sort=new#comments`" :aria-current="sort === 'new' ? 'true' : undefined">最新</a>
        <a :href="`${pageUrl}?sort=top#comments`" :aria-current="sort === 'top' ? 'true' : undefined">最热</a>
      </nav>
    </div>

    <p v-if="!commentsEnabled" class="mt-4 text-sm text-fg-2">这篇文章关闭了评论。</p>
    <template v-else-if="interactive">
      <div v-if="postProblems.length" class="c-notice c-notice--info mt-4">
        <CIcon name="info" />
        <ul class="c-notice__body">
          <li v-for="problem in postProblems" :key="problem">{{ problem }}</li>
        </ul>
      </div>
      <CCommentComposer v-if="canPost" @send="emit('create', $event)" />
    </template>
    <p v-else class="mt-4 text-sm text-fg-2">
      <a :href="loginUrl" class="font-semibold text-fg underline underline-offset-4 hover:text-primary-text">登录后评论</a>
    </p>

    <ol id="comment-list" class="c-comments__list">
      <CCommentItem
        v-for="item in thread.comments"
        :key="item?.id"
        :item="item!"
        :interactive="interactive"
        :can-post="canPost"
        :can-moderate="canModerate"
        :viewer-id="viewerId"
        @like="emit('like', $event)"
        @reply="emit('reply', $event)"
        @edit="emit('edit', $event)"
        @remove="emit('remove', $event)"
        @hide="emit('hide', $event)"
        @pin="emit('pin', $event)"
      />
      <li v-if="!thread.comments.length" class="py-6 text-sm text-fg-3">还没有评论。</li>
    </ol>

    <div id="comments-more" class="mt-6">
      <a v-if="hasMore" :href="`${pageUrl}?comments=${nextPage}&sort=${sort}#comments`" class="c-btn c-btn--secondary c-btn--sm" @click.prevent="emit('more', nextPage)">加载更多</a>
    </div>
  </section>
</template>
