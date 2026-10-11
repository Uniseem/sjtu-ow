<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
type Choice = "system" | "light" | "dark"
type Theme = { current: () => Choice; set: (choice: Choice) => void }
const current = ref<Choice>("system")
const menu = ref<HTMLDetailsElement | null>(null)
const choices: Array<{ value: Choice; label: string; icon: string }> = [
  { value: "system", label: "跟随系统", icon: "monitor" },
  { value: "light", label: "浅色", icon: "sun" },
  { value: "dark", label: "深色", icon: "moon" },
]
function theme(): Theme | undefined { return (window as Window & { owTheme?: Theme }).owTheme }
function sync(): void { current.value = theme()?.current() || "system" }
function select(choice: Choice): void { theme()?.set(choice); sync(); if (menu.value) menu.value.open = false }
onMounted(() => { sync(); document.addEventListener("owthemechange", sync) })
onUnmounted(() => document.removeEventListener("owthemechange", sync))
</script>
<template>
  <details ref="menu" class="c-theme">
    <summary class="c-iconbtn" aria-label="颜色模式" title="颜色模式"><span class="c-theme__light"><CIcon name="sun" /></span><span class="c-theme__dark"><CIcon name="moon" /></span></summary>
    <div class="c-menu__panel" role="group" aria-label="颜色模式"><button v-for="choice in choices" :key="choice.value" type="button" :aria-pressed="current === choice.value" @click="select(choice.value)"><CIcon :name="choice.icon" />{{ choice.label }}</button></div>
  </details>
</template>
