<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue"
import { owTheme, type ThemeChoice } from "../theme"
import CIcon from "./CIcon.vue"

// Colour mode (design 13.2.1). The choices live in the masthead menu and,
// on phones, in the drawer. Hidden until hydration: without the script the
// system decides and the buttons could do nothing anyway. The hidden
// attribute is static in the template and removed after mount, so server
// and browser paint the same thing.
const props = withDefaults(defineProps<{ variant: "bar" | "drawer" }>(), { variant: "bar" })
const current = ref<ThemeChoice>("system")
const root = ref<HTMLElement | null>(null)
const choices: { value: ThemeChoice; label: string; icon: string }[] = [
  { value: "system", label: "跟随系统", icon: "monitor" },
  { value: "light", label: "浅色", icon: "sun" },
  { value: "dark", label: "深色", icon: "moon" },
]

function pick(choice: ThemeChoice) {
  owTheme()?.set(choice)
  current.value = choice
  // The masthead menu closes; the drawer stays open to show the change.
  if (props.variant === "bar" && root.value instanceof HTMLDetailsElement) root.value.open = false
}

function sync() {
  current.value = owTheme()?.current() ?? "system"
}

let onThemeChange: (() => void) | null = null
onMounted(() => {
  root.value?.removeAttribute("hidden")
  sync()
  onThemeChange = sync
  document.addEventListener("owthemechange", onThemeChange)
})
onUnmounted(() => {
  if (onThemeChange) document.removeEventListener("owthemechange", onThemeChange)
})
</script>
<template>
  <details v-if="variant === 'bar'" ref="root" class="c-theme max-sm:hidden" hidden>
    <summary class="c-iconbtn" aria-label="颜色模式" title="颜色模式">
      <span class="c-theme__light"><CIcon name="sun" /></span>
      <span class="c-theme__dark"><CIcon name="moon" /></span>
    </summary>
    <div class="c-menu__panel" role="group" aria-label="颜色模式">
      <button
        v-for="choice in choices"
        :key="choice.value"
        type="button"
        :aria-pressed="String(choice.value === current)"
        @click="pick(choice.value)"
      >
        <CIcon :name="choice.icon" />{{ choice.label }}
      </button>
    </div>
  </details>
  <div v-else ref="root" class="sm:hidden" hidden>
    <p class="c-eyebrow mt-8">颜色模式</p>
    <div class="c-drawer__theme" role="group" aria-label="颜色模式">
      <button
        v-for="choice in choices"
        :key="choice.value"
        type="button"
        :aria-pressed="String(choice.value === current)"
        @click="pick(choice.value)"
      >
        <CIcon :name="choice.icon" />{{ choice.label }}
      </button>
    </div>
  </div>
</template>
