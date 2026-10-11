<script setup lang="ts">
import { nextTick, ref } from "vue"
import { imageUrl } from "@sjtu-ow/shared/media"
import type { Image } from "../../pages/content/types"
import ImagePicker from "./ImagePicker.vue"
withDefaults(defineProps<{ modelValue: number | null; name: string; label: string; disabled?: boolean }>(), { disabled: false })
const emit = defineEmits<{ "update:modelValue": [value: number | null] }>()
const picking = ref(false)
const button = ref<HTMLButtonElement | null>(null)
function selected(image: Image): void {
  emit("update:modelValue", image.id)
  close()
}
function close(): void {
  picking.value = false
  void nextTick(() => button.value?.focus())
}
</script>
<template>
  <div class="b-picker">
    <input type="hidden" :name="name" :value="modelValue ?? ''">
    <span v-if="modelValue" class="b-picker__preview"><img :src="imageUrl(modelValue, 'fill-400x400')" :alt="label" width="160" height="160" loading="lazy"></span>
    <span v-else class="b-sub">未选图片</span>
    <div class="b-rowacts">
      <button ref="button" type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="disabled" @click="picking = true">选择</button>
      <button v-if="modelValue" type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="disabled" @click="$emit('update:modelValue', null)">清除</button>
    </div>
    <ImagePicker v-if="picking" @select="selected" @close="close" />
  </div>
</template>
