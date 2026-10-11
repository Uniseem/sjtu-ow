<script setup lang="ts">
import CIcon from "./CIcon.vue"
import type { SaveState } from "@sjtu-ow/shared/autosave"

withDefaults(defineProps<{
  state: SaveState
  message?: string
  dirty?: boolean
  pending?: boolean
  loginRequired?: boolean
  loginHref?: string
}>(), {
  message: "",
  dirty: false,
  pending: false,
  loginRequired: false,
  loginHref: "/accounts/login/",
})

defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="c-formbar">
    <p
      class="c-autosave"
      :data-state="state"
      data-autosave-status
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <CIcon v-if="state === 'failed' || state === 'partial'" name="alert" />
      <span>{{ message || (dirty ? '尚未保存' : '') }}</span>
      <a
        v-if="loginRequired"
        :href="loginHref"
        target="_blank"
        rel="noopener"
        class="c-link"
      >重新登录</a>
    </p>
    <button
      v-if="dirty && !pending && (state === 'failed' || state === 'partial')"
      type="button"
      class="c-btn c-btn--quiet c-btn--sm"
      @click="$emit('retry')"
    >重新保存</button>
  </div>
</template>
