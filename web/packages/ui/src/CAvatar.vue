<script setup lang="ts">
import { computed } from "vue"
import { hue, initial } from "@sjtu-ow/shared/initial"
import { imageUrl } from "@sjtu-ow/shared/media"
import type { AvatarPerson } from "./types"
const props = defineProps<{ person: AvatarPerson; size?: "xs" | "sm" | "md" | "lg"; plain?: boolean }>()
const src = computed(() => {
  if (props.person.is_active === false) return ""
  const spec = props.size === "md" || props.size === "lg" ? "fill-176x176" : "fill-88x88"
  if (props.person.is_active !== false) {
    if (props.person.avatar_image_id) return imageUrl(props.person.avatar_image_id, spec)
    if (props.person.avatar_url) return props.person.avatar_url
  }
  if (props.person.default_avatar_image_id) return imageUrl(props.person.default_avatar_image_id, spec)
  return props.person.default_avatar_url || ""
})
</script>
<template>
  <span :class="['c-avatar', size && `c-avatar--${size}`, !plain && `c-hue-${hue(person.id)}`]" aria-hidden="true"><img v-if="src" :src="src" alt="" loading="lazy"><template v-else>{{ initial(person.nickname) }}</template></span>
</template>
