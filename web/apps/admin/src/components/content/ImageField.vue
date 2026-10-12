<script setup lang="ts">
import { nextTick, ref, watch } from "vue"
import { getApiImagesId } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useContentResource } from "../../pages/content/use-resource"
import { imageUrl } from "@sjtu-ow/shared/media"
import type { Image } from "../../pages/content/types"
import ImagePicker from "./ImagePicker.vue"
const props = withDefaults(defineProps<{ modelValue: number | null; name: string; label: string; disabled?: boolean }>(), { disabled: false })
const emit = defineEmits<{ "update:modelValue": [value: number | null] }>()
const api = useAdminApi()
const image = useContentResource(async signal => props.modelValue ? getApiImagesId(api, props.modelValue, { signal }) : null, false)
watch(() => props.modelValue, () => { void image.load() }, { immediate: true })
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
  <div class="b-picker" role="group" :aria-label="label">
    <input type="hidden" :name="name" :value="modelValue ?? ''">
    <div class="b-picker__preview"><img v-if="modelValue" :src="imageUrl(modelValue, 'max-320x200')" alt="" loading="lazy"></div>
    <div class="b-picker__body">
      <p class="b-picker__title">{{ modelValue ? image.data.value?.title || (image.pending.value ? '正在加载…' : '图片暂时无法加载') : '没有选图片' }}</p>
      <div class="b-picker__actions">
      <button ref="button" type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="disabled" :aria-label="`选择${label}`" @click="picking = true">选择</button>
      <button v-if="modelValue" type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="disabled" :aria-label="`清除${label}`" @click="$emit('update:modelValue', null)">清除</button>
      </div>
    </div>
    <ImagePicker v-if="picking" @select="selected" @close="close" />
  </div>
</template>
