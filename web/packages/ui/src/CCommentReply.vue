<script setup lang="ts">
import CAvatar from "./CAvatar.vue"
import CCommentComposer from "./CCommentComposer.vue"
import CIcon from "./CIcon.vue"
import { owDate, owISO, owTime } from "@sjtu-ow/shared/time"
import type { CommentView, CommentReplySubmission, CommentEditSubmission } from "./types"
import { useConfirm } from "@sjtu-ow/shared/confirm"
const confirm = useConfirm()

// comments/templates/comments/_reply.html: one nested answer, one level deep.
defineProps<{
  reply: CommentView
  interactive: boolean
  canPost: boolean
  canModerate: boolean
  viewerId?: number | null
}>()
const emit = defineEmits<{
  like: [id: number]
  reply: [payload: CommentReplySubmission]
  edit: [comment: CommentEditSubmission]
  remove: [id: number]
  hide: [change: { id: number; hidden: boolean }]
}>()
</script>
<template>
  <li :id="`comment-${reply.id}`" class="c-comment c-comment--reply">
    <p v-if="reply.is_deleted" class="c-comment__placeholder">回复已删除。</p>
    <template v-else-if="reply.is_hidden && !canModerate">
      <p class="c-comment__placeholder">该回复已隐藏。</p>
    </template>
    <template v-else>
      <CAvatar :person="{ id: reply.user_id ?? undefined, nickname: reply.author_name }" size="sm" plain />
      <div class="min-w-0">
        <p class="c-comment__meta">
          <span class="c-comment__name">{{ reply.author_name }}</span>
          <time :datetime="owISO(new Date(reply.created_at))" class="font-numeric">{{ owDate(new Date(reply.created_at)) }} {{ owTime(new Date(reply.created_at)) }}</time>
          <span v-if="reply.is_hidden" class="c-status c-status--off">已隐藏</span>
          <span v-if="reply.edited_at">已编辑</span>
        </p>
        <p class="c-comment__body"><span v-if="reply.reply_to_user_name" class="c-comment__at">@{{ reply.reply_to_user_name }}</span> {{ reply.content }}</p>
        <div class="c-comment__actions">
          <button v-if="interactive" type="button" class="c-act" :aria-pressed="reply.liked_by_me ? 'true' : 'false'" @click="emit('like', reply.id)">
            <CIcon name="heart" />{{ reply.liked_by_me ? "已赞" : "赞" }} <span class="font-numeric" data-like-count>{{ reply.like_count }}</span>
          </button>
          <span v-else class="c-act"><CIcon name="heart" />赞 <span class="font-numeric" data-like-count>{{ reply.like_count }}</span></span>
          <template v-if="interactive">
            <details v-if="canPost">
              <summary class="c-act"><CIcon name="reply" />回复</summary>
              <CCommentComposer :parent-name="reply.author_name" @send="emit('reply', { ...$event, parentId: reply.id })" />
            </details>
            <template v-if="reply.user_id === viewerId && !reply.is_hidden">
              <details>
                <summary class="c-act"><CIcon name="edit" />编辑</summary>
                <CCommentComposer editing :draft="reply.content" class="mt-2" @send="emit('edit', { ...$event, id: reply.id })" />
              </details>
              <button type="button" class="c-act c-act--danger" @click="confirm('删除这条评论？删除后不能恢复。') && emit('remove', reply.id)">
                <CIcon name="trash" />删除
              </button>
            </template>
            <template v-if="canModerate">
              <button v-if="reply.is_hidden" type="button" class="c-act" @click="emit('hide', { id: reply.id, hidden: false })">
                <CIcon name="eye" />恢复
              </button>
              <button v-else type="button" class="c-act c-act--danger" @click="confirm('隐藏这条回复？') && emit('hide', { id: reply.id, hidden: true })">
                <CIcon name="eye-off" />隐藏
              </button>
            </template>
          </template>
        </div>
      </div>
    </template>
  </li>
</template>
