<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>

<template>
  <div class="wrap">
    <nav><RouterLink to="/">首页</RouterLink><RouterLink to="/teams/1/">战队一</RouterLink></nav>
    <div class="noscript-banner" role="status">页面脚本没有加载成功，部分按钮暂时用不了，请刷新。</div>
    <slot />
  </div>
</template>
