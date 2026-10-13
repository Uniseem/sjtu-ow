<script setup lang="ts">
import type { SetupCheck } from "../../pages/management/pending"
import { localHref } from "../../pages/management/format"
defineProps<{ items: SetupCheck[]; kind: 'required' | 'optional' | 'done' }>()
</script>
<template>
  <ul class="b-list b-checks" :class="{ 'mt-3': kind === 'optional' }" :data-setup="kind">
    <li v-for="item in items" :key="item.label">
      <span class="c-tag" :class="{ 'c-tag--accent': kind === 'required' }">{{ kind === 'required' ? '必做' : kind === 'optional' ? '建议' : '已完成' }}</span>
      <span>
        <template v-if="kind === 'done'">{{ item.label }}：{{ item.detail }}</template>
        <template v-else><strong>
          <a v-if="item.url && localHref(item.url)" class="c-link" :href="localHref(item.url)">{{ item.label }}</a>
          <template v-else>{{ item.label }}</template>
        </strong>：{{ item.detail }}</template></span>
      </li>
    </ul>
</template>
