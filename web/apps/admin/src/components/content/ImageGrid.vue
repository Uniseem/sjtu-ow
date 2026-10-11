<script setup lang="ts">
import { imageUrl } from "@sjtu-ow/shared/media"
import type { Image, Collection } from "../../pages/content/types"
withDefaults(defineProps<{ images: Image[]; collections?: Collection[]; choose?: boolean; disabled?: boolean }>(), {
  collections: () => [], choose: false, disabled: false,
})
defineEmits<{ select: [image: Image] }>()
function collectionName(id: number | null, collections: Collection[]): string {
  return collections.find((collection) => collection.id === id)?.name ?? "未分集合"
}
</script>
<template>
  <ul class="b-grid">
    <li v-for="image in images" :key="image.id">
      <button v-if="choose" type="button" class="b-grid__item" :disabled="disabled" :aria-label="`选择图片：${image.title}`" @click="$emit('select', image)">
        <span class="b-grid__pic"><img :src="imageUrl(image.id, 'fill-400x400')" alt="" loading="lazy" width="400" height="400"></span>
        <span class="b-grid__name">{{ image.title }}</span>
        <span class="b-grid__meta">{{ collectionName(image.collection_id, collections) }} · {{ image.width }}×{{ image.height }}</span>
      </button>
      <RouterLink v-else class="b-grid__item" :to="`/admin/images/${image.id}/`">
        <span class="b-grid__pic"><img :src="imageUrl(image.id, 'fill-400x400')" alt="" loading="lazy" width="400" height="400"></span>
        <span class="b-grid__name">{{ image.title }}</span>
        <span class="b-grid__meta">{{ collectionName(image.collection_id, collections) }} · {{ image.width }}×{{ image.height }}</span>
      </RouterLink>
    </li>
  </ul>
</template>
