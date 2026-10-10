<script setup lang="ts">
import CAvatar from "./CAvatar.vue"
import CIcon from "./CIcon.vue"
import type { AvatarPerson } from "./types"
withDefaults(defineProps<{
  title: string; user: AvatarPerson; current: string
  nav: { href: string; label: string; available: boolean; icon: string }[]
  gaps?: { label: string; href: string; hint: string }[]; waiting?: number
}>(), { gaps: () => [], waiting: 0 })
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead">
      <div class="l-container l-container--narrow">
        <nav class="c-crumbs" aria-label="位置"><a href="/">首页</a><span class="c-crumbs__sep">/</span><span>个人中心</span></nav>
        <div class="c-pagehead__row">
          <div><h1>{{ title }}</h1><p class="c-pagehead__meta gap-2"><CAvatar :person="user" size="sm" plain /><span class="font-semibold text-fg">{{ user.nickname }}</span><a :href="`/members/${user.id}/`" class="c-link text-sm" data-own-page>我的主页</a></p></div>
          <div class="c-pagehead__actions"><slot name="actions" /></div>
        </div>
      </div>
    </header>
    <div class="l-container l-container--narrow pt-6 pb-16 lg:pt-10 lg:pb-24">
      <div class="grid gap-8 lg:grid-cols-[13rem_minmax(0,1fr)] lg:gap-14">
        <nav aria-label="个人中心" class="font-nav min-w-0">
          <ul class="c-sidenav hidden self-start lg:block">
            <li v-for="item in nav" :key="item.href">
              <a v-if="item.available" :href="item.href" :aria-current="current === item.href ? 'page' : undefined"><CIcon :name="item.icon" class="size-5 c-sidenav__icon" />{{ item.label }}</a>
              <span v-else class="flex min-h-11 items-center pl-4 text-fg-3">{{ item.label }}</span>
            </li>
          </ul>
          <div class="c-tabs lg:hidden"><template v-for="item in nav" :key="item.href"><a v-if="item.available" :href="item.href" :aria-current="current === item.href ? 'page' : undefined">{{ item.label }}</a></template></div>
        </nav>
        <div class="flex min-w-0 flex-col gap-10">
          <div id="profile-incomplete">
            <div v-if="gaps.length" class="c-notice c-notice--warn" role="status">
              <CIcon name="alert" /><div class="c-notice__body"><p class="font-semibold">资料尚未完整，报名赛事和内战前需要补全：</p><ul class="mt-1 list-[square] pl-5"><li v-for="gap in gaps" :key="gap.href"><a :href="gap.href">{{ gap.label }}</a><span class="text-fg-2"> — {{ gap.hint }}</span></li></ul></div>
            </div>
          </div>
          <div v-if="waiting" class="c-notice c-notice--info" role="status" data-held-reminder><CIcon name="info" /><div class="c-notice__body">有 {{ waiting }} 件事的信还没决定发不发。<a href="/letters/" class="c-link">去看看</a></div></div>
          <slot />
        </div>
      </div>
    </div>
  </main>
</template>
