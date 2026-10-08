<script setup lang="ts">
import { initial } from "../initial"
import { useViewer } from "../viewer"
import CIcon from "./CIcon.vue"

// The masthead's account area: 登录/注册 for visitors, the member's own
// menu once signed in (design 13.3). The avatar is the initial on the base
// disk for now; real pictures come with the avatar API (M3).
const viewer = useViewer()
const user = viewer.user
</script>
<template>
  <details v-if="user" class="c-menu">
    <summary :aria-label="`账号菜单：${user.nickname}`">
      <span class="c-avatar c-avatar--sm" aria-hidden="true">{{ initial(user.nickname) }}</span>
      <span class="hidden max-w-[8rem] truncate sm:inline">{{ user.nickname }}</span>
      <CIcon name="chevron-down" class="size-4 text-fg-2" />
    </summary>
    <div class="c-menu__panel">
      <template v-if="user.admin">
        <a href="/admin/" data-admin-link>管理后台</a>
        <hr />
      </template>
      <a href="/me/">个人中心</a>
      <a href="/me/registrations/">我的报名</a>
      <a href="/me/teams/">我的战队</a>
      <hr />
      <a href="/accounts/logout/">退出</a>
    </div>
  </details>
  <template v-else>
    <a href="/accounts/login/" class="c-account__link">登录</a>
    <a href="/accounts/signup/" class="c-btn c-btn--primary c-btn--sm hidden sm:inline-flex">注册</a>
  </template>
</template>
