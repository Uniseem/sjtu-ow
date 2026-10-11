<script setup lang="ts">
import type { ArticleDraft } from "../../pages/content/types"
import { publicationMissing, localDateTime } from "../../pages/content/types"
import { computed } from "vue"
const props = defineProps<{ draft: ArticleDraft; pending: boolean }>()
defineEmits<{ publish: []; cancel: [] }>()
const missing = computed(() => publicationMissing(props.draft))
</script>
<template>
  <section class="c-notice c-notice--info" role="region" aria-label="发布确认">
    <div class="c-notice__body">
      <h2 class="b-section__title">{{ draft.go_live_at ? '安排上线' : '发布文章' }}</h2>
      <p v-if="missing.length">还缺：{{ missing.join('、') }}。补齐以后再发布。</p>
      <template v-else>
        <p v-if="draft.go_live_at">文章将在 {{ localDateTime(draft.go_live_at).replace('T', ' ') }}（北京时间）上线。</p>
        <p v-else>发布后，网站上的文章会更新为这份草稿。</p>
        <p v-if="draft.expire_at">定时下线：{{ localDateTime(draft.expire_at).replace('T', ' ') }}（北京时间）。</p>
      </template>
      <div class="b-actions">
        <button type="button" class="c-btn c-btn--primary" :disabled="missing.length > 0 || pending" @click="$emit('publish')">{{ pending ? '正在提交…' : draft.go_live_at ? '安排上线' : '确认发布' }}</button>
        <button type="button" class="c-btn c-btn--secondary" :disabled="pending" @click="$emit('cancel')">继续编辑</button>
      </div>
    </div>
  </section>
</template>
