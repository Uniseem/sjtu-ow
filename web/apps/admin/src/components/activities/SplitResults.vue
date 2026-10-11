<script setup lang="ts">
import { computed, nextTick, ref } from "vue"
import type { ScrimBoard } from "../../pages/activities/domain"
import type { SplitValues } from "../../pages/activities/split-model"
import { bestTarget, sideProblems, sideTotal, splitZones } from "../../pages/activities/split-model"
import BoardCard from "./BoardCard.vue"
import AdminNotice from "../AdminNotice.vue"
import { useSortableBoard } from "./use-sortable-board"

const props = defineProps<{
  board: ScrimBoard
  values: SplitValues
  disabled: boolean
}>()
const emit = defineEmits<{
  move: [id: number, zone: string]
  warning: [message: string]
}>()
const root = ref<HTMLElement | null>(null)
const zones = computed(() => splitZones(props.board, props.values))
const buffer = computed(() => zones.value.find((zone) => zone.key === "buffer"))
const sides = computed(() => (["a", "b"] as const).map((side) => ({
  key: side,
  label: side === "a" ? "A 队" : "B 队",
  total: sideTotal(zones.value, side),
  zones: zones.value.filter((zone) => zone.team === side),
  problems: sideProblems(zones.value, props.board.scrim?.format ?? "rq_5v5", side),
})))
const gap = computed(() => Math.abs(sideTotal(zones.value, "a") - sideTotal(zones.value, "b")))

function moved(id: number, zone: string): void {
  emit("move", id, zone)
  void nextTick(() => root.value?.querySelector<HTMLElement>(`[data-signup="${id}"]`)?.focus())
}

function side(id: number, target: "a" | "b" | ""): void {
  const signup = props.board.signups.find((item) => item.signup_id === id)
  if (!signup) return
  const zone = bestTarget(zones.value, signup, target)
  if (!zone) {
    emit("warning", "队伍满员时不能直接移进去，先把要换下来的人移到缓冲区。")
    return
  }
  moved(id, zone.key)
}

useSortableBoard(root, () => [props.values, props.board.board_version], () => !props.disabled,
  (id, zone) => moved(id, zone), (message) => emit("warning", message))
</script>

<template>
  <section ref="root" class="b-form" data-split-board>
    <h2 class="b-section__title">分队结果</h2>
    <p class="b-section__text">A 队总分 <strong>{{ sides[0]?.total }}</strong> · B 队总分 <strong>{{ sides[1]?.total }}</strong> · 分差 <strong>{{ gap }}</strong></p>
    <AdminNotice message="拖动卡片换队伍和位置。队伍满员时不能直接拖进去——先把要换下来的人拖到下面的缓冲区，再把新人拖进来。不用鼠标的话，每张卡片上的按钮也能移动。" kind="info" />
    <div class="split-teams">
      <div v-for="team in sides" :key="team.key" class="split-team" :data-team-panel="team.key">
        <h3 class="b-section__title">{{ team.label }}（总分 {{ team.total }}）</h3>
        <p v-if="team.problems.length" class="split-problem" role="status">{{ team.problems.join('、') }}</p>
        <section v-for="zone in team.zones" :key="zone.key" class="split-zone">
          <h4 class="split-zone-title">{{ zone.label }}<span v-if="zone.capacity">（{{ zone.members.length }}/{{ zone.capacity }}）</span></h4>
          <ul class="split-list" :data-board-zone="zone.key" :aria-label="`${team.label} ${zone.label}`">
            <BoardCard v-for="signup in zone.members" :key="signup.signup_id" :signup="signup" :zones="zones" :disabled="disabled" @move="moved" @side="side" />
          </ul>
        </section>
      </div>
    </div>
    <div v-if="buffer" class="split-buffer">
      <h3 class="split-zone-title">缓冲区（不上场）</h3>
      <ul class="split-list" data-board-zone="buffer" aria-label="缓冲区（不上场）">
        <BoardCard v-for="signup in buffer.members" :key="signup.signup_id" :signup="signup" :zones="zones" :disabled="disabled" @move="moved" @side="side" />
      </ul>
      <p class="b-sub">队伍满了要换人，先把人拖到这里腾位置。留在这里的人这次不上场。</p>
    </div>
    <p class="b-formbar__note">位置人数不符合规格时会标红，但仍然可以保存。</p>
  </section>
</template>
