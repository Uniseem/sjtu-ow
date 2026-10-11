<script setup lang="ts">
import { computed, onMounted, onUnmounted } from "vue"
import { useRoute } from "vue-router"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CAvatar from "@sjtu-ow/ui/CAvatar.vue"
import AdminTheme from "./AdminTheme.vue"
import { useAdminSession } from "../core/session"
import type { AdminSection, AdminTab } from "../core/api"
const route = useRoute()
const session = useAdminSession()
const sections = computed(() => session.nav.value)
const user = computed(() => session.user.value)
function selected(item: AdminSection | AdminTab): boolean {
  const path = item.url.split("?")[0]
  return (path === "/admin/" ? route.path === path : route.path.startsWith(path)) || item.tabs.some(selected)
}
function closeMenus(event: MouseEvent): void {
  const inside = event.target instanceof Element ? event.target.closest("details") : null
  for (const details of document.querySelectorAll<HTMLDetailsElement>("details.c-menu[open],details.c-theme[open]")) if (details !== inside) details.open = false
}
function escape(event: KeyboardEvent): void {
  if (event.key !== "Escape") return
  const menu = document.querySelector<HTMLDetailsElement>("details.c-menu[open],details.c-theme[open]")
  if (menu) { menu.open = false; menu.querySelector("summary")?.focus() }
}
onMounted(() => { document.addEventListener("click",closeMenus); document.addEventListener("keydown",escape) })
onUnmounted(() => { document.removeEventListener("click",closeMenus); document.removeEventListener("keydown",escape) })
</script>
<template>
  <header class="b-top">
    <div class="b-top__bar">
      <a href="/admin/" class="b-brand" aria-label="管理后台首页"><svg class="b-brand__mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false"><rect width="32" height="32" rx="9" class="fill-primary" /><path d="M8 21.5l8-8 8 8" fill="none" class="stroke-white" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" /></svg><span>管理后台</span></a>
      <nav class="b-nav" aria-label="后台大类"><a v-for="section in sections" :key="section.key" class="b-nav__link" :href="section.url" :aria-current="selected(section) ? 'page' : undefined">{{ section.label }}</a></nav>
      <div class="b-account">
        <a class="b-top__site" href="/" target="_blank" rel="noopener"><CIcon name="external" class="size-4" /><span>打开网站</span></a>
        <AdminTheme />
        <details v-if="user" class="c-menu">
          <summary :aria-label="'账号菜单：' + user.nickname"><CAvatar :person="user" size="sm" plain /><span class="b-account__name">{{ user.nickname }}</span><CIcon name="chevron-down" class="size-4" /></summary>
          <div class="c-menu__panel"><a href="/me/">个人中心</a><hr><a href="/accounts/logout/">退出</a></div>
        </details>
      </div>
    </div>
  </header>
</template>
