<script setup lang="ts">
import CIcon from "./CIcon.vue"
defineProps<{ tank?: boolean; damage?: boolean; support?: boolean }>()
</script>
<template>
  <span class="c-roles">
    <span v-if="tank" class="c-role"><CIcon name="role-tank" class="size-3.5" />坦克</span>
    <span v-if="damage" class="c-role"><CIcon name="role-damage" class="size-3.5" />输出</span>
    <span v-if="support" class="c-role"><CIcon name="role-support" class="size-3.5" />支援</span>
  </span>
</template>
