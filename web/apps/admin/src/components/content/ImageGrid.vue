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
        <span class="b-grid__pic"><img :src="imageUrl(image.id, 'max-320x240')" alt="" loading="lazy"></span>
        <span class="b-grid__name">{{ image.title }}</span>
        <span class="b-grid__meta">{{ collectionName(image.collection_id, collections) }}<template v-if="!choose"> · {{ image.width }}×{{ image.height }}</template></span>
      </button>
      <RouterLink v-else class="b-grid__item" :to="`/admin/images/${image.id}/`">
        <span class="b-grid__pic"><img :src="imageUrl(image.id, 'max-320x240')" alt="" loading="lazy"></span>
        <span class="b-grid__name">{{ image.title }}</span>
        <span class="b-grid__meta">{{ collectionName(image.collection_id, collections) }}<template v-if="!choose"> · {{ image.width }}×{{ image.height }}</template></span>
      </RouterLink>

    </li>
  </ul>
</template>
