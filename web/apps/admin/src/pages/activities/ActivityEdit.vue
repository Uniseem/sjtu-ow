<script setup lang="ts">
import { showReadError } from "../../core/read-error"
import { computed, onMounted, onUnmounted, shallowRef, watch } from "vue"
import { useRoute } from "vue-router"
import { ApiError, getApiAdminScrimsId, getApiAdminTournamentsId } from "@sjtu-ow/api"
import type { GetApiAdminScrimsIdOut, GetApiAdminTournamentsIdOut } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import AdminPage from "../../components/AdminPage.vue"
import AdminNotice from "../../components/AdminNotice.vue"
import TournamentEditor from "../../components/activities/TournamentEditor.vue"
import ScrimEditor from "../../components/activities/ScrimEditor.vue"
import { activityHref, activityLabel, numericId } from "./domain"
import type { ActivityKind } from "./domain"
import { getScrimCopyPreview, getTournamentCopyPreview, getScrimDefaults, getTournamentDefaults } from "./pending"

const props = defineProps<{ kind: ActivityKind; mode: "new" | "edit" | "copy" }>()
const api = useAdminApi()
const route = useRoute()
const tournamentDefaults = shallowRef<import("./pending").TournamentDefaults | undefined>(undefined)
const scrimDefaults = shallowRef<import("./pending").ScrimDefaults | undefined>(undefined)
const tournament = shallowRef<GetApiAdminTournamentsIdOut | null>(null)
const scrim = shallowRef<GetApiAdminScrimsIdOut | null>(null)
const pending = shallowRef(true)
const error = shallowRef("")
const title = computed(() => {
  const name = tournament.value?.tournament?.title ?? scrim.value?.scrim?.title ?? ""
  if (props.mode === "new") return `新建${activityLabel(props.kind)}`
  if (props.mode === "copy") return `复制${activityLabel(props.kind)}：${name}`
  return name || `（未命名${activityLabel(props.kind)}）`
})
let request: AbortController | null = null
let sequence = 0

async function load(): Promise<void> {
  request?.abort()
  request = new AbortController()
  const token = ++sequence
  pending.value = true
  error.value = ""
  tournament.value = null
  scrim.value = null
  const id = numericId(route.params.id)
  try {
    if (props.mode === "new") {
      if (props.kind === "tournaments") {
        const defaults = await getTournamentDefaults(api, { signal: request.signal })
        if (sequence === token) tournamentDefaults.value = defaults
      } else {
        const defaults = await getScrimDefaults(api, { signal: request.signal })
        if (sequence === token) scrimDefaults.value = defaults
      }
      return
    }
    if (!id) throw new ApiError(404, "not_found", "找不到这个页面")
    if (props.kind === "tournaments") {
      const value = props.mode === "copy"
        ? await getTournamentCopyPreview(api, id, { signal: request.signal })
        : await getApiAdminTournamentsId(api, id, { signal: request.signal })
      if (sequence !== token) return
      if (!value.tournament) throw new ApiError(404, "not_found", "找不到这个页面")
      tournament.value = value
    } else {
      const value = props.mode === "copy"
        ? await getScrimCopyPreview(api, id, { signal: request.signal })
        : await getApiAdminScrimsId(api, id, { signal: request.signal })
      if (sequence !== token) return
      if (!value.scrim) throw new ApiError(404, "not_found", "找不到这个页面")
      scrim.value = value
    }
  } catch (failure) {
    if (sequence !== token || request.signal.aborted) return
    showReadError(failure)
    error.value = failure instanceof Error ? failure.message : "暂时无法打开，请稍后再试。"
  } finally {
    if (sequence === token) pending.value = false
  }
}

onMounted(load)
watch(() => [route.params.id, props.kind, props.mode], load)
onUnmounted(() => { sequence += 1; request?.abort() })
</script>

<template>
  <AdminPage :title="title" section="events" :back-href="activityHref(kind)">
    <p v-if="pending" role="status">正在加载…</p>
    <AdminNotice v-else-if="error" :message="error" kind="error" />
    <template v-else>
      <TournamentEditor v-if="kind === 'tournaments'" :key="`${mode}-${route.params.id ?? 'new'}`" :detail="tournament" :defaults="tournamentDefaults" :mode="mode" />
      <ScrimEditor v-else :key="`${mode}-${route.params.id ?? 'new'}`" :detail="scrim" :defaults="scrimDefaults" :mode="mode" />
    </template>
    <button v-if="error" type="button" class="c-btn c-btn--secondary" @click="load">重试</button>
  </AdminPage>
</template>
