<script setup lang="ts">
import { computed, watch } from "vue"
import { useRoute } from "vue-router"
import { useAdminSession } from "../core/session"

const props = defineProps<{
  title: string
  section: string
  backHref?: string
  subtitle?: string
}>()
const route = useRoute()
const session = useAdminSession()
const current = computed(() => session.nav.value.find((section) => section.key === props.section || section.label === props.section))
const tabs = computed(() => current.value?.tabs ?? [])

function selected(url: string): boolean {
  if (url === "/admin/") return route.path === url
  return route.path === url || route.path.startsWith(url)
}
watch(() => props.title, (title) => {
  document.title = `${title} · 管理后台`
}, { immediate: true })
</script>

<template>
  <header class="b-head">
    <div class="b-head__inner">
      <p class="b-head__kicker">{{ current?.label }}</p>
      <div class="b-head__row">
        <div>
          <p v-if="backHref" class="mb-2"><a :href="backHref" class="c-link">返回列表</a></p>
          <h1 class="b-head__title" tabindex="-1">{{ title }}</h1>
          <p v-if="subtitle" class="mt-2 text-sm text-fg-2">{{ subtitle }}</p>
        </div>
        <div class="b-head__actions"><slot name="actions" /></div>
      </div>
      <nav v-if="tabs.length > 1 && !backHref" class="b-tabs" aria-label="页面">
        <a v-for="tab in tabs" :key="tab.key" :href="tab.url" :aria-current="selected(tab.url) ? 'page' : undefined">
          {{ tab.label }}<span v-if="tab.count" class="c-tabs__count">{{ tab.count }}</span>
        </a>
      </nav>
    </div>
  </header>
  <slot name="subtabs" />
  <main id="main" class="b-main"><slot /></main>
</template>
