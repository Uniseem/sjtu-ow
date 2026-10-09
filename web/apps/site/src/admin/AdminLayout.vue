<script setup lang="ts">
import { computed } from "vue"
import { useRoute } from "vue-router"
import { useViewer } from "../viewer"
import { ADMIN_SECTIONS, sectionForPath } from "./nav"
import CIcon from "../components/CIcon.vue"
import ThemeMenu from "../components/ThemeMenu.vue"

const route = useRoute()
const viewer = useViewer()

const allowedSections = computed(() => {
  return ADMIN_SECTIONS.filter((s) => s.allowed(viewer.user))
})

const currentSection = computed(() => {
  return sectionForPath(route.path)
})
</script>

<template>
  <div class="min-h-screen bg-bg text-fg flex flex-col">
    <!-- 顶栏 b-top -->
    <header class="b-top">
      <div class="b-top__bar">
        <a href="/admin/" class="b-brand" aria-label="SJTU-OW 管理后台首页">
          <svg class="b-brand__mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
            <rect width="32" height="32" rx="8" class="fill-primary" />
            <path
              d="M8 21.5l8-8 8 8"
              fill="none"
              class="stroke-white"
              stroke-width="3.2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          <span class="text-base font-bold tracking-tight text-white">SJTU-OW <span class="text-xs font-normal opacity-80 ml-1">管理后台</span></span>
        </a>

        <nav class="b-nav" aria-label="后台主导航">
          <a
            v-for="sec in allowedSections"
            :key="sec.id"
            :href="sec.path"
            class="b-nav__link"
            :aria-current="currentSection?.id === sec.id ? 'page' : undefined"
          >
            {{ sec.label }}
          </a>
        </nav>

        <div class="b-account">
          <a href="/" class="b-top__site">
            <CIcon name="arrow-up-right" class="size-4" />
            <span>打开网站</span>
          </a>
          <ThemeMenu />
          <span v-if="viewer.user" class="b-account__name text-sm opacity-90">
            {{ viewer.user.nickname }}
          </span>
          <a v-if="viewer.user" href="/accounts/logout/" class="c-btn c-btn--ghost c-btn--sm">
            退出
          </a>
        </div>
      </div>
    </header>

    <!-- 鉴权拦截 -->
    <div v-if="!viewer.user" class="b-main text-center py-16">
      <div class="c-notice c-notice--warning max-w-md mx-auto">
        <p class="font-medium">需要登录后才能访问管理后台</p>
      </div>
      <div class="mt-6">
        <a :href="`/accounts/login/?next=${encodeURIComponent(route.fullPath)}`" class="c-btn c-btn--primary">
          前往登录
        </a>
      </div>
    </div>
    <div v-else-if="!viewer.user.admin" class="b-main text-center py-16">
      <div class="c-notice c-notice--danger max-w-md mx-auto">
        <p class="font-bold text-lg">403 没有权限</p>
        <p class="mt-2 text-sm">你没有进入管理后台的权限。</p>
      </div>
      <div class="mt-6">
        <a href="/" class="c-btn c-btn--secondary">返回网站首页</a>
      </div>
    </div>
    <div v-else class="flex-1">
      <slot />
    </div>
  </div>
</template>
