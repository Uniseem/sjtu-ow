<script setup lang="ts">
import { ref } from "vue"
import type { TournamentEntry } from "../../pages/activities/domain"
import { boardRank, record, roleLabel } from "../../pages/activities/domain"
import type { TeamZone } from "../../pages/activities/team-board-model"

const props = defineProps<{
  entry: TournamentEntry
  targets: TeamZone[]
  disabled: boolean
  current: string
}>()
const emit = defineEmits<{ move: [id: number, zoneKey: string] }>()
const destination = ref("")

function keyboard(event: KeyboardEvent): void {
  if (props.disabled || !event.altKey || event.ctrlKey || event.metaKey) return
  const index = props.targets.findIndex((target) => target.key === props.current)
  if (event.key === "ArrowDown") {
    event.preventDefault()
    emit("move", props.entry.signup_id, "")
    return
  }
  if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return
  event.preventDefault()
  const step = event.key === "ArrowRight" ? 1 : -1
  const next = props.targets[index + step]
  if (next) emit("move", props.entry.signup_id, next.key)
}
</script>

<template>
  <li
    class="split-card"
    :class="{ 'is-blocked': entry.conflict }"
    :data-signup="entry.signup_id"
    tabindex="0"
    :aria-label="`${entry.nickname}，${entry.battletag}。Alt 加左右箭头换队，Alt 加下箭头移回散人池。`"
    @keydown="keyboard"
  >
    <span class="split-card-name" data-drag-handle>{{ entry.nickname }}{{ record(entry)?.is_active === false ? '（账号已停用）' : '' }}</span>
    <span class="split-card-tag b-mono">{{ entry.battletag || '游戏 ID 已删除' }}</span>
    <span v-if="record(entry)?.is_sjtu === false" class="split-card-flag">校外</span>
    <span class="split-card-roles">
      <span v-for="(role, index) in entry.roles" :key="role">
        {{ index ? ' · ' : '' }}{{ roleLabel(role) }} {{ boardRank(role === 'tank' ? entry.rank_tank : role === 'damage' ? entry.rank_damage : entry.rank_support) }}
      </span>
    </span>
    <span v-if="entry.conflict" class="split-card-blocked">{{ entry.conflict }}</span>
    <span class="split-card-moves">
      <button
        v-for="target in targets"
        :key="target.key"
        type="button"
        class="c-btn c-btn--secondary c-btn--sm"
        :disabled="disabled || Boolean(entry.conflict) || target.key === current"
        @click="emit('move', entry.signup_id, target.key)"
      >{{ target.name || '新队伍' }}</button>
      <button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="disabled || !current" @click="emit('move', entry.signup_id, '')">散人池</button>
    </span>
    <div v-if="targets.length > 5" class="split-card-moves">
      <label :for="`destination-${entry.signup_id}`" class="b-sub">移动到</label>
      <select :id="`destination-${entry.signup_id}`" v-model="destination" class="c-input" :disabled="disabled">
        <option value="">散人池</option>
        <option v-for="target in targets" :key="target.key" :value="target.key">{{ target.name || '新队伍' }}</option>
      </select>
      <button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="disabled" @click="emit('move', entry.signup_id, destination)">移动</button>
    </div>
  </li>
</template>
