<script setup lang="ts">
import { imageUrl } from "@sjtu-ow/shared/media"
import { SECTION_PICTURES, type Section } from "@sjtu-ow/shared/pictures"
withDefaults(defineProps<{ section: Section; imageId?: number | null; imageClass?: string }>(), { imageClass: "c-pagehead__img" })
</script>
<template>
  <img v-if="imageId" :class="imageClass" :src="imageUrl(imageId, section === 'home' ? 'fill-2400x1350' : 'fill-2400x640')" alt="" :width="2400" :height="section === 'home' ? 1350 : 640">
  <template v-else>
    <img v-for="mode in (['light', 'dark'] as const)" :key="mode" :class="[imageClass, 'c-scene', mode === 'light' ? 'c-scene--light' : 'c-scene--dark']" :src="`/static/img/placeholders/${SECTION_PICTURES[section][mode]}`" alt="" :width="2400" :height="section === 'home' ? 1350 : 640">
  </template>
</template>
