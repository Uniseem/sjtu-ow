<script setup lang="ts">
import { useRoute } from "vue-router"
import { NAV, sectionOf } from "../sections"
import AccountArea from "./AccountArea.vue"
import BrandMark from "./BrandMark.vue"
import CIcon from "./CIcon.vue"
import SLink from "./SLink.vue"
import ThemeMenu from "./ThemeMenu.vue"

// The masthead (design 13.3): brand, main nav, the search box that joins
// from 1280px, the colour mode menu, the account area, and on phones the
// drawer. The loadbar rides along its lower edge.
const route = useRoute()
const current = () => sectionOf(route.path)
</script>
<template>
  <header class="c-masthead">
    <div class="l-container c-masthead__bar">
      <BrandMark />
      <nav class="c-nav font-nav" aria-label="主导航">
        <SLink v-for="item in NAV" :key="item.to" :to="item.to" :current="current() === item.section">
          {{ item.label }}
        </SLink>
      </nav>
      <form action="/search/" method="get" role="search" class="c-masthead__search">
        <input type="search" name="q" maxlength="50" placeholder="搜索文章、赛事、战队、成员" aria-label="站内搜索" />
        <button type="submit" aria-label="搜索"><CIcon name="search" /></button>
      </form>
      <div class="c-masthead__end">
        <a href="/search/" class="c-iconbtn c-masthead__find" aria-label="搜索"><CIcon name="search" /></a>
        <ThemeMenu variant="bar" />
        <div class="c-account"><AccountArea /></div>
        <details class="c-drawer lg:hidden">
          <summary class="c-iconbtn -mr-2.5" aria-label="导航菜单">
            <span class="c-drawer__open"><CIcon name="menu" class="size-6" /></span>
            <span class="c-drawer__close"><CIcon name="close" class="size-6" /></span>
          </summary>
          <div class="c-drawer__panel">
            <nav class="c-drawer__nav font-nav" aria-label="主导航">
              <SLink v-for="item in NAV" :key="item.to" :to="item.to" :current="current() === item.section">
                {{ item.label }}
              </SLink>
            </nav>
            <form action="/search/" method="get" role="search" class="c-drawer__search">
              <input type="search" name="q" maxlength="50" placeholder="搜索" aria-label="站内搜索" />
              <button type="submit" class="c-btn c-btn--secondary">搜索</button>
            </form>
            <ThemeMenu variant="drawer" />
            <p class="c-eyebrow mt-8">更多</p>
            <nav class="mt-3 grid grid-cols-2 gap-x-6 font-nav" aria-label="更多">
              <a href="/submit/" class="flex min-h-11 items-center text-fg-2">我要投稿</a>
              <a href="/me/" class="flex min-h-11 items-center text-fg-2">个人中心</a>
              <a href="/about/" class="flex min-h-11 items-center text-fg-2">关于我们</a>
              <a href="/privacy/" class="flex min-h-11 items-center text-fg-2">隐私政策</a>
            </nav>
          </div>
        </details>
      </div>
    </div>
    <div class="c-loadbar" aria-hidden="true"></div>
  </header>
</template>
