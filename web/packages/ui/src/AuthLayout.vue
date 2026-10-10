<script setup lang="ts">
import AuthWhy from "./AuthWhy.vue"
defineProps<{ why?: boolean }>()
</script>
<template>
  <main id="main" class="flex-1">
    <div class="l-container l-container--narrow pt-10 pb-20 lg:pt-16 lg:pb-28">
      <div class="grid items-start gap-12 lg:grid-cols-[minmax(0,28rem)_minmax(0,1fr)] lg:gap-24">
        <section class="c-auth"><slot /></section>
        <AuthWhy v-if="why" /><slot v-else name="aside" />
      </div>
    </div>
  </main>
</template>
