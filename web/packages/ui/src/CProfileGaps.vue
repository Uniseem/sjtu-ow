<script setup lang="ts">
defineProps<{ gaps: { label: string; href: string }[] }>()
</script>
<template>
  <p v-if="gaps.length" class="mt-2">去补全：<template v-for="(gap, i) in gaps" :key="gap.href"><a :href="gap.href" class="c-link">{{ gap.label }}</a><template v-if="i < gaps.length - 1">、</template></template></p>
</template>
