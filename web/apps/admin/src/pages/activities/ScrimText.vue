<script setup lang="ts">
import { showReadError } from "../../core/read-error"
import { onMounted, shallowRef } from "vue"
import { useRoute } from "vue-router"
import { ApiError, getApiAdminScrimsIdBoard } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import AdminNotice from "../../components/AdminNotice.vue"
import { numericId } from "./domain"

const api = useAdminApi()
const route = useRoute()
const id = numericId(route.params.id)
const text = shallowRef("")
const pending = shallowRef(true)
const error = shallowRef("")

async function load(): Promise<void> {
  pending.value = true
  error.value = ""
  try {
    if (!id) throw new ApiError(404, "not_found", "找不到这个页面")
    const result = await getApiAdminScrimsIdBoard(api, id)
    if (!result.scrim) throw new ApiError(404, "not_found", "找不到这个页面")
    text.value = result.copy_text
  } catch (failure) {
    showReadError(failure)
    error.value = failure instanceof Error ? failure.message : "暂时无法加载，请稍后再试。"
  } finally {
    pending.value = false
  }
}

onMounted(load)
</script>

<template>
  <p v-if="pending" role="status">正在加载…</p>
  <AdminNotice v-else-if="error" :message="error" kind="error" />
  <pre v-else>{{ text }}</pre>
</template>
