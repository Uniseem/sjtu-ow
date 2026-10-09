<script setup lang="ts">
import { computed } from "vue"
import { useViewer } from "../viewer"
import { isTabVisible, type AdminTab } from "./nav"
import CIcon from "../components/CIcon.vue"

const props = defineProps<{
  kicker?: string
  title: string
  backTo?: string
  backLabel?: string
  tabs?: AdminTab[]
  activeTab?: string
  subtabs?: { id: string; label: string; path: string }[]
  activeSubtab?: string
}>()

const viewer = useViewer()

const visibleTabs = computed(() => {
  if (!props.tabs) return []
  return props.tabs.filter((t) => isTabVisible(t, viewer.user))
})
</script>

<template>
  <div class="b-head border-b border-border">
    <div class="b-head__inner">
      <div v-if="backTo" class="mb-1">
        <a :href="backTo" class="b-head__back">
          <CIcon name="arrow-left" class="size-4" />
          <span>{{ backLabel ?? "返回列表" }}</span>
        </a>
      </div>
      <div v-else-if="kicker" class="b-head__kicker">
        {{ kicker }}
      </div>

      <div class="b-head__row">
        <h1 class="b-head__title">{{ title }}</h1>
        <div class="b-head__actions">
          <slot name="actions" />
        </div>
      </div>

      <nav v-if="visibleTabs.length > 1" class="b-tabs" aria-label="页面标签导航">
        <a
          v-for="t in visibleTabs"
          :key="t.id"
          :href="t.path"
          :aria-current="activeTab === t.id ? 'page' : undefined"
        >
          {{ t.label }}
        </a>
      </nav>
    </div>

    <nav v-if="subtabs && subtabs.length > 1" class="b-subtabs pb-3" aria-label="二级标签导航">
      <a
        v-for="st in subtabs"
        :key="st.id"
        :href="st.path"
        :aria-current="activeSubtab === st.id ? 'page' : undefined"
      >
        {{ st.label }}
      </a>
    </nav>
  </div>
</template>
