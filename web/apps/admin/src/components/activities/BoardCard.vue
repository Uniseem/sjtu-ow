<script setup lang="ts">
import { ref } from "vue"
import type { ScrimSignup } from "../../pages/activities/domain"
import { record, roleLabel } from "../../pages/activities/domain"
import type { SplitZone } from "../../pages/activities/split-model"
import { keyboardSide } from "../../pages/activities/split-model"

const props = defineProps<{
  signup: ScrimSignup
  zones: SplitZone[]
  disabled: boolean
}>()
const emit = defineEmits<{
  move: [id: number, zoneKey: string]
  side: [id: number, side: "a" | "b" | ""]
}>()
const target = ref("buffer")

function keyboard(event: KeyboardEvent): void {
  if (props.disabled) return
  const team = keyboardSide(event)
  if (team === null) return
  event.preventDefault()
  emit("side", props.signup.signup_id, team)
}
</script>

<template>
  <li
    class="split-card"
    :data-signup="signup.signup_id"
    tabindex="0"
    :aria-label="`${signup.nickname}，${signup.battletag}。Alt 加左右箭头换队，Alt 加下箭头移到缓冲区。`"
    @keydown="keyboard"
  >
    <span class="split-card-name" data-drag-handle>{{ signup.nickname }}{{ record(signup)?.is_active === false ? '（账号已停用）' : '' }}</span>
    <span class="split-card-tag b-mono">{{ signup.battletag }}</span>
    <span class="split-card-rank">{{ signup.rating_used ?? '—' }}</span>
    <span class="split-card-roles">
      <template v-for="(role, index) in signup.roles" :key="role">
        {{ index ? ' · ' : '' }}{{ signup.rank_text[role] || `${roleLabel(role)}：${signup.ratings[role] ?? '—'}` }}
      </template>
    </span>
    <span class="split-card-moves">
      <button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="disabled" @click="emit('side', signup.signup_id, 'a')">A</button>
      <button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="disabled" @click="emit('side', signup.signup_id, 'b')">B</button>
      <button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="disabled" @click="emit('side', signup.signup_id, '')">缓冲</button>
    </span>
    <div class="split-card-moves">
      <label :for="`target-${signup.signup_id}`" class="b-sub">移动到</label>
      <select :id="`target-${signup.signup_id}`" v-model="target" class="c-input" :disabled="disabled">
        <option v-for="zone in zones" :key="zone.key" :value="zone.key">{{ zone.team ? `${zone.team === 'a' ? 'A' : 'B'} 队 · ` : '' }}{{ zone.label }}</option>
      </select>
      <button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="disabled" @click="emit('move', signup.signup_id, target)">移动</button>
    </div>
  </li>
</template>
