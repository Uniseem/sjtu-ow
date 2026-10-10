<script setup lang="ts">
import { imageUrl } from "@sjtu-ow/shared/media"
import { hue, initial } from "@sjtu-ow/shared/initial"
defineProps<{ team: { id: number; name: string; logo_image_id?: number | null } }>()
</script>
<template>
  <div class="flex items-center gap-4" data-team-logo>
    <span :class="`c-teams__logo c-teams__logo--lg c-hue-${hue(team.id)}`"><img v-if="team.logo_image_id" :src="imageUrl(team.logo_image_id, 'fill-288x288')" alt=""><template v-else>{{ initial(team.name) }}</template></span>
    <p class="text-sm text-fg-2">{{ team.logo_image_id ? '现在的队标。选一个新文件就换上，勾「删除队标」就删掉。' : '还没有队标，选一个图片文件就传上去。' }}</p>
  </div>
</template>
