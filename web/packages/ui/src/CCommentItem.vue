<script setup lang="ts">
import CAvatar from "./CAvatar.vue"
import CCommentComposer from "./CCommentComposer.vue"
import CCommentReply from "./CCommentReply.vue"
import CIcon from "./CIcon.vue"
import { owDate, owISO, owTime } from "@sjtu-ow/shared/time"
import type { CommentView } from "./types"

// comments/templates/comments/_item.html: a top-level comment, its replies
// folded into a details the same way.
defineProps<{
  item: CommentView
  interactive: boolean
  canPost: boolean
  canModerate: boolean
  viewerId?: number | null
}>()
const emit = defineEmits<{
  like: [id: number]
  reply: [payload: { parentId: number; content: string }]
  edit: [comment: { id: number; content: string }]
  remove: [id: number]
  hide: [change: { id: number; hidden: boolean }]
  pin: [change: { id: number; pinned: boolean }]
}>()
</script>
<template>
  <li :id="`comment-${item.id}`" class="c-comment" :class="{ 'is-pinned': item.is_pinned }">
    <p v-if="item.is_deleted" class="c-comment__placeholder">评论已删除。</p>
    <template v-else-if="item.is_hidden && !canModerate">
      <p class="c-comment__placeholder">该评论已隐藏。</p>
    </template>
    <template v-else>
      <CAvatar :person="{ id: item.user_id ?? undefined, nickname: item.author_name }" plain />
      <div class="min-w-0">
        <p class="c-comment__meta">
          <span class="c-comment__name">{{ item.author_name }}</span>
          <time :datetime="owISO(new Date(item.created_at))" class="font-numeric">{{ owDate(new Date(item.created_at)) }} {{ owTime(new Date(item.created_at)) }}</time>
          <span v-if="item.is_pinned" class="c-tag c-tag--accent">置顶</span>
          <span v-if="item.is_hidden" class="c-status c-status--off">已隐藏</span>
          <span v-if="item.edited_at">已编辑</span>
        </p>
        <p class="c-comment__body">{{ item.content }}</p>
        <div class="c-comment__actions">
          <button v-if="interactive" type="button" class="c-act" :aria-pressed="item.liked_by_me ? 'true' : 'false'" @click="emit('like', item.id)">
            <CIcon name="heart" />{{ item.liked_by_me ? "已赞" : "赞" }} <span class="font-numeric" data-like-count>{{ item.like_count }}</span>
          </button>
          <span v-else class="c-act"><CIcon name="heart" />赞 <span class="font-numeric" data-like-count>{{ item.like_count }}</span></span>
          <template v-if="interactive">
            <details v-if="canPost">
              <summary class="c-act"><CIcon name="reply" />回复</summary>
              <CCommentComposer :parent-name="item.author_name" @send="emit('reply', { parentId: item.id, content: $event.content })" />
            </details>
            <template v-if="item.user_id === viewerId && !item.is_hidden">
              <details>
                <summary class="c-act"><CIcon name="edit" />编辑</summary>
                <CCommentComposer editing :draft="item.content" class="mt-2" @send="emit('edit', { id: item.id, content: $event.content })" />
              </details>
              <button type="button" class="c-act c-act--danger" @click="confirm('删除这条评论？删除后不能恢复。') && emit('remove', item.id)">
                <CIcon name="trash" />删除
              </button>
            </template>
            <template v-if="canModerate">
              <button v-if="item.is_pinned" type="button" class="c-act" @click="emit('pin', { id: item.id, pinned: false })">
                <CIcon name="pin" />取消置顶
              </button>
              <button v-else type="button" class="c-act" @click="emit('pin', { id: item.id, pinned: true })">
                <CIcon name="pin" />置顶
              </button>
              <button v-if="item.is_hidden" type="button" class="c-act" @click="emit('hide', { id: item.id, hidden: false })">
                <CIcon name="eye" />恢复
              </button>
              <button v-else type="button" class="c-act c-act--danger" @click="confirm('隐藏这条评论？') && emit('hide', { id: item.id, hidden: true })">
                <CIcon name="eye-off" />隐藏
              </button>
            </template>
          </template>
        </div>
      </div>
    </template>
    <details v-if="item.replies?.length" class="c-comment__thread">
      <summary>{{ item.replies.length }} 条回复<CIcon name="chevron-down" /></summary>
      <ol>
        <CCommentReply
          v-for="reply in item.replies"
          :key="reply.id"
          :reply="reply"
          :interactive="interactive"
          :can-post="canPost"
          :can-moderate="canModerate"
          :viewer-id="viewerId"
          @like="emit('like', $event)"
          @reply="emit('reply', $event)"
          @edit="emit('edit', $event)"
          @remove="emit('remove', $event)"
          @hide="emit('hide', $event)"
        />
      </ol>
    </details>
  </li>
</template>
