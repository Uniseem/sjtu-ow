<script setup lang="ts">
defineProps<{ title: string; heading: string; lede: string }>()
</script>

<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead">
      <div class="l-container l-container--narrow">
        <nav class="c-crumbs" aria-label="位置">
          <a href="/">首页</a>
          <span class="c-crumbs__sep">/</span>
          <span>{{ title }}</span>
        </nav>
        <h1>{{ heading }}</h1>
        <p class="c-pagehead__lede">{{ lede }}</p>
      </div>
    </header>
    <div class="l-container l-container--narrow pt-8 pb-16 lg:pb-24">
      <slot />
    </div>
  </main>
</template>
