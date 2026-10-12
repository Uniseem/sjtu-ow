<script setup lang="ts">
import { computed, watch } from "vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import { useRoute } from "vue-router"
import { useAdminSession } from "../core/session"

const props = defineProps<{
  title: string
  documentTitle?: string
  section: string
  backHref?: string
  backLabel?: string
  subtitle?: string
}>()
const route = useRoute()
const session = useAdminSession()
const current = computed(() => session.nav.value.find((section) => section.key === props.section || section.label === props.section))
const backText = computed(() => props.backLabel ?? session.nav.value.flatMap(section => [section, ...section.tabs, ...section.tabs.flatMap(tab => tab.tabs ?? [])]).find(item => item.url === props.backHref)?.label ?? "返回")
const tabs = computed(() => current.value?.tabs ?? [])

function selected(url: string): boolean {
  if (url === "/admin/") return route.path === url
  return route.path === url || route.path.startsWith(url)
}
watch(() => [props.title, props.documentTitle], ([title, documentTitle]) => {
  document.title = `${documentTitle || title} · 管理后台`
}, { immediate: true })
</script>

<template>
  <header class="b-head">
    <div class="b-head__inner">
      <a v-if="backHref" class="b-head__back" :href="backHref"><CIcon name="arrow-left" class="size-4" />{{ backText }}</a>
      <p v-else-if="current" class="b-head__kicker">{{ current.label }}</p>
      <div class="b-head__row">
        <h1 class="b-head__title" tabindex="-1">{{ title }}</h1>
        <div class="b-head__actions"><slot name="actions" /></div>
      </div>
      <p v-if="subtitle" class="mt-2 text-sm text-fg-2">{{ subtitle }}</p>
      <nav v-if="tabs.length && !backHref" class="b-tabs" :aria-label="current?.label">
        <a v-for="tab in tabs" :key="tab.key" :href="tab.url" :aria-current="selected(tab.url) ? 'page' : undefined">
          {{ tab.label }}<span v-if="tab.count" class="c-tabs__count">{{ tab.count }}</span>
        </a>
      </nav>
    </div>
  </header>
  <slot name="subtabs" />
  <main id="main" class="b-main"><slot /></main>
</template>
