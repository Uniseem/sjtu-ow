<script setup lang="ts">
import { showReadError } from "../../core/read-error"
import { onMounted, onUnmounted, shallowRef } from "vue"
import { useRoute } from "vue-router"
import { ApiError, getApiAdminTournamentsId, getApiAdminTournamentsIdBoard } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import AdminPage from "../../components/AdminPage.vue"
import AdminNotice from "../../components/AdminNotice.vue"
import TeamBoardController from "../../components/activities/TeamBoardController.vue"
import type { TournamentBoard } from "./domain"
import { numericId } from "./domain"

const api = useAdminApi()
const route = useRoute()
const id = numericId(route.params.id)
const board = shallowRef<TournamentBoard | null>(null)
const minimum = shallowRef(1)
const pending = shallowRef(true)
const error = shallowRef("")
let request: AbortController | null = null

async function load(): Promise<void> {
  request?.abort()
  request = new AbortController()
  const controller = request
  pending.value = true
  error.value = ""
  try {
    if (!id) throw new ApiError(404, "not_found", "找不到这个页面")
    const [result, detail] = await Promise.all([
      getApiAdminTournamentsIdBoard(api, id, { signal: controller.signal }),
      getApiAdminTournamentsId(api, id, { signal: controller.signal }),
    ])
    if (controller.signal.aborted) return
    if (!result.tournament || !detail.tournament) throw new ApiError(404, "not_found", "找不到这个页面")
    board.value = result
    minimum.value = detail.tournament.roster_min
  } catch (failure) {
    if (controller.signal.aborted) return
    showReadError(failure)
    error.value = failure instanceof Error ? failure.message : "暂时无法加载，请稍后再试。"
  } finally {
    if (!controller.signal.aborted) pending.value = false
  }
}

onMounted(load)
onUnmounted(() => request?.abort())
</script>

<template>
  <AdminPage :title="board ? `队伍编排：${board.tournament?.title ?? ''}` : '队伍编排'" section="events" back-href="/admin/tournaments/">
    <p v-if="pending" role="status">正在加载…</p>
    <AdminNotice v-else-if="error" :message="error" kind="error" />
    <TeamBoardController v-else-if="board" :initial="board" :minimum="minimum" :id="id" />
    <button v-if="error" type="button" class="c-btn c-btn--secondary" @click="load">重试</button>
  </AdminPage>
</template>
