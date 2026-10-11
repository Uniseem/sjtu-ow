<script setup lang="ts">
import { computed } from "vue"
import MeLayout from "@sjtu-ow/ui/MeLayout.vue"
import { PERSONAL_NAV, readRecord } from "../personal"
import type { ViewerUser } from "../viewer"

const props = defineProps<{ title: string; current: string; user: ViewerUser }>()
const context = computed(() => readRecord(props.user))
const person = computed(() => ({
  id: props.user.id,
  nickname: props.user.nickname,
  avatar_image_id: typeof context.value?.avatar_image_id === "number" ? context.value.avatar_image_id : undefined,
  avatar_url: typeof context.value?.avatar_url === "string" ? context.value.avatar_url : undefined,
  default_avatar_image_id: typeof context.value?.default_avatar_image_id === "number" ? context.value.default_avatar_image_id : undefined,
  is_active: true,
}))
const gaps = computed(() => {
  const entries = context.value?.profile_gaps
  if (!Array.isArray(entries)) return []
  return entries.flatMap((entry: unknown) => {
    const gap = readRecord(entry)
    if (!gap || typeof gap.label !== "string" || typeof gap.href !== "string" || typeof gap.hint !== "string") return []
    return [{ label: gap.label, href: gap.href, hint: gap.hint }]
  })
})
const waiting = computed(() => typeof context.value?.waiting_letters === "number" ? context.value.waiting_letters : 0)
</script>

<template>
  <MeLayout :title="title" :current="current" :user="person" :nav="PERSONAL_NAV" :gaps="gaps" :waiting="waiting">
    <template #actions><slot name="actions" /></template>
    <slot />
  </MeLayout>
</template>
