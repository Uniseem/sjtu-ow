<script setup lang="ts">
import { showReadError } from "../../core/read-error"
import { computed, onMounted, onUnmounted, shallowRef, watch } from "vue"
import { useRoute } from "vue-router"
import { ApiError, getApiAdminScrimsIdBoard } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import AdminPage from "../../components/AdminPage.vue"
import AdminNotice from "../../components/AdminNotice.vue"
import SplitController from "../../components/activities/SplitController.vue"
import type { ScrimBoard } from "./domain"
import { numericId, queryText } from "./domain"

const api = useAdminApi()
const route = useRoute()
const id = computed(() => numericId(route.params.id))
const order = computed(() => queryText(route.query.order) || "created")
const board = shallowRef<ScrimBoard | null>(null)
const pending = shallowRef(true)
const message = shallowRef("")
let sequence = 0
let request: AbortController | null = null

async function load(): Promise<void> {
  request?.abort()
  request = new AbortController()
  const token = ++sequence
  pending.value = true
  message.value = ""
  board.value = null
  try {
    if (!id.value) throw new ApiError(404, "not_found", "找不到这个页面")
    const result = await getApiAdminScrimsIdBoard(api, id.value, { order: order.value }, { signal: request.signal })
    if (sequence !== token) return
    if (!result.scrim) throw new ApiError(404, "not_found", "找不到这个页面")
    board.value = result
  } catch (error) {
    if (sequence !== token || request.signal.aborted) return
    showReadError(error)
    message.value = error instanceof Error ? error.message : "暂时无法加载，请稍后再试。"
  } finally {
    if (sequence === token) pending.value = false
  }
}

onMounted(load)
watch(() => [id.value, order.value], load)
onUnmounted(() => { sequence += 1; request?.abort() })
</script>

<template>
  <AdminPage :title="board ? `分队：${board.scrim?.title ?? ''}` : '分队'" section="activities" back-href="/admin/scrims/">
    <p v-if="pending" role="status">正在加载…</p>
    <AdminNotice v-else-if="message" :message="message" kind="error" />
    <SplitController v-else-if="board" :key="`${id}-${order}`" :initial="board" :id="id" />
    <button v-if="message" type="button" class="c-btn c-btn--secondary" @click="load">重试</button>
  </AdminPage>
</template>
