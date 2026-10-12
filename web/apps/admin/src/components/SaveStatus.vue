<script setup lang="ts">
import CAutosave from "@sjtu-ow/ui/CAutosave.vue"
import { useRoute } from "vue-router"
import type { SaveSnapshot } from "@sjtu-ow/shared/autosave"

withDefaults(defineProps<{
  snapshot: Pick<SaveSnapshot<object>, "state" | "message" | "loginRequired">
  dirty: boolean
  pending: boolean
  idleMessage?: string
}>(), { idleMessage: "改了就自动保存" })
defineEmits<{ retry: [] }>()
const route = useRoute()
</script>

<template>
  <CAutosave
    bare
    :idle-message="idleMessage"
    :state="snapshot.state"
    :message="snapshot.message"
    :dirty="dirty"
    :pending="pending"
    :login-required="snapshot.loginRequired"
    :login-href="'/accounts/login/?next=' + encodeURIComponent(route.fullPath)"
    @retry="$emit('retry')"
  />
</template>
