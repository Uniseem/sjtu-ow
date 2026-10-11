<script setup lang="ts">
import { computed, ref } from "vue"
import { revisionLines } from "../../pages/content/revision-diff"
import type { ArticleDraft } from "../../pages/content/types"
const props = defineProps<{ before: ArticleDraft; after: ArticleDraft }>()
const showAll = ref(false)
const labels: Record<keyof ArticleDraft, string> = {
  title: "标题",
  slug: "网址片段",
  category_id: "分类",
  cover_image_id: "封面",
  summary: "摘要",
  body_md: "正文",
  author_id: "作者",
  comments_enabled: "开放评论",
  related_tournament_id: "关联赛事",
  seo_title: "SEO 标题",
  search_description: "搜索描述",
  go_live_at: "定时上线",
  expire_at: "定时下线",
}
const changes = computed(() => (Object.keys(labels) as (keyof ArticleDraft)[])
  .filter((key) => key !== "body_md" && props.before[key] !== props.after[key]))
const lines = computed(() => revisionLines(props.before.body_md, props.after.body_md))
const visible = computed(() => {
  if (showAll.value) return lines.value
  const changed = new Set<number>()
  lines.value.forEach((line, index) => {
    if (line.kind !== "same") {
      for (let offset = Math.max(0, index - 2); offset <= Math.min(lines.value.length - 1, index + 2); offset++) changed.add(offset)
    }
  })
  return lines.value.filter((_, index) => changed.has(index))
})
function value(raw: ArticleDraft[keyof ArticleDraft]): string {
  if (raw === null || raw === "") return "（空）"
  if (typeof raw === "boolean") return raw ? "是" : "否"
  return String(raw)
}
</script>
<template>
  <section class="b-section" aria-label="和最新草稿比较">
    <h2 class="b-section__title">和最新草稿比较</h2>
    <p class="c-field__help">左边是这份修订，右边是最新草稿。恢复修订只会存成草稿。</p>
    <table v-if="changes.length" class="c-table c-table--stack">
      <thead><tr><th>字段</th><th>这份修订</th><th>最新草稿</th></tr></thead>
      <tbody><tr v-for="key in changes" :key="key"><td>{{ labels[key] }}</td><td data-label="这份修订">{{ value(before[key]) }}</td><td data-label="最新草稿">{{ value(after[key]) }}</td></tr></tbody>
    </table>
    <p v-if="before.body_md === after.body_md" class="b-sub">正文没有变化。</p>
    <template v-else>
      <label class="c-check"><input v-model="showAll" type="checkbox">显示完整正文</label>
      <table class="c-table" aria-label="正文差异">
        <thead><tr><th>修订行号</th><th>草稿行号</th><th>变化</th><th>正文</th></tr></thead>
        <tbody>
          <tr v-for="(line, index) in visible" :key="`${line.before}-${line.after}-${index}`">
            <td class="is-num">{{ line.before ?? '—' }}</td>
            <td class="is-num">{{ line.after ?? '—' }}</td>
            <td>{{ line.kind === 'added' ? '新增' : line.kind === 'removed' ? '删除' : '不变' }}</td>
            <td><code>{{ line.text || ' ' }}</code></td>
          </tr>
        </tbody>
      </table>
    </template>
    <p v-if="!changes.length && before.body_md === after.body_md" class="b-section__text">这份修订和最新草稿一致。</p>
  </section>
</template>
