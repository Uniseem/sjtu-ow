<script setup lang="ts">
import { rankParts } from "@sjtu-ow/shared/display"
withDefaults(defineProps<{ label?: string | null }>(), { label: "" })
</script>
<template>
  <span v-if="!label || label === '未定级'" class="c-rank c-rank--none">未定级</span>
  <span v-else class="c-rank">{{ rankParts(label)[0] }}<template v-if="rankParts(label)[1]">{{ " " }}<span class="c-rank__div">{{ rankParts(label)[1] }}</span></template></span>
</template>
