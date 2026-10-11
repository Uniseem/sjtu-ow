<script setup lang="ts">
import type { UploadItem } from "../../pages/content/use-upload-queue"
import { humanBytes } from "../../pages/content/types"
defineProps<{ items: UploadItem[]; pending: boolean }>()
function title(event: Event, key: string): void {
  if (event.target instanceof HTMLInputElement) emit("rename", key, event.target.value)
}
const emit = defineEmits<{ remove: [key: string]; rename: [key: string, title: string] }>()
</script>
<template>
  <table v-if="items.length" class="c-table c-table--stack">
    <thead><tr><th>图片</th><th>标题</th><th>大小</th><th>状态</th><th><span class="sr-only">操作</span></th></tr></thead>
    <tbody>
      <tr v-for="item in items" :key="item.key">
        <td>{{ item.file.name }}</td>
        <td data-label="标题"><input class="c-input" :value="item.title" :disabled="pending || item.state !== 'queued'" :aria-label="`${item.file.name}的标题`" maxlength="255" @input="title($event, item.key)"></td>
        <td data-label="大小">{{ humanBytes(item.file.size) }}</td>
        <td data-label="状态"><span :role="item.state === 'failed' || item.state === 'uncertain' ? 'alert' : 'status'">{{ item.message || '待上传' }}</span></td>
        <td>
          <RouterLink v-if="item.image" class="c-link" :to="`/admin/images/${item.image.id}/`">编辑</RouterLink>
          <button v-else-if="item.state !== 'uncertain'" type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="pending" @click="$emit('remove', item.key)">移除</button>
        </td>
      </tr>
    </tbody>
  </table>
</template>
