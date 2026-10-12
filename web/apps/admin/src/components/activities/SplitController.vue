<script setup lang="ts">
import { computed, shallowRef } from "vue"
import {
  ApiError,
  postApiAdminScrimsIdBoardGenerate,
  postApiAdminScrimsIdBoardSelection,
  postApiAdminScrimsIdBoardTeams,
} from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminSave } from "../../core/use-save"
import { useAdminAction } from "../../core/use-action"
import type { ScrimBoard } from "../../pages/activities/domain"
import { boardRank, formatLabel, orderOptions, record, roleLabel, shortTimestamp, teamSize, timestamp } from "../../pages/activities/domain"
import { boardFromCurrent, currentSplit, moveSignup, orderedBoard, splitValues } from "../../pages/activities/split-model"
import type { SplitValues } from "../../pages/activities/split-model"
import SplitResults from "./SplitResults.vue"
import AdminNotice from "../AdminNotice.vue"
import SaveStatus from "../SaveStatus.vue"

const props = defineProps<{ initial: ScrimBoard; id: number }>()
const api = useAdminApi()
const board = shallowRef(props.initial)
const warning = shallowRef("")
const clipboardMessage = shallowRef("")
const generating = shallowRef(false)
const save = useAdminSave<SplitValues>({
  initial: splitValues(props.initial),
  version: props.initial.board_version,
  readCurrent: (value) => {
    const parsed = boardFromCurrent(value)
    if (parsed) board.value = orderedBoard(parsed, props.initial.order)
    return currentSplit(value)
  },
  available: () => !generating.value,
  transport: async (body, key, signal) => {
    let version = body.base_version
    let current = board.value
    const saved: string[] = []
    if (Object.hasOwn(body.changes, "signup_ids")) {
      current = await postApiAdminScrimsIdBoardSelection(api, props.id, {
        signup_ids: body.changes.signup_ids ?? [],
        base_board_version: version,
      }, { key: `${key}:selection`, signal, unauthorized: "throw" })
      version = current.board_version
      saved.push("signup_ids")
      current = orderedBoard(current, props.initial.order)
      board.value = current
    }
    if (Object.hasOwn(body.changes, "placements")) {
      const validIds = new Set(current.signups.map((signup) => signup.signup_id))
      const selectedIds = new Set(current.signups.filter((signup) => signup.is_selected).map((signup) => signup.signup_id))
      const placements = (body.changes.placements ?? []).filter((placement) => validIds.has(placement.signup_id)).map((placement) => (
        selectedIds.has(placement.signup_id) ? placement : { signup_id: placement.signup_id, team: "", role: "" }
      ))
      current = await postApiAdminScrimsIdBoardTeams(api, props.id, {
        placements,
        base_board_version: version,
      }, { key: `${key}:teams`, signal, unauthorized: "throw" })
      version = current.board_version
      saved.push("placements")
      current = orderedBoard(current, props.initial.order)
      board.value = current
    }
    return { version, saved, values: splitValues(current) }
  },
})
const { snapshot, values, fields, pending, dirty } = save
const generator = useAdminAction<{ signup_ids: number[]; base_board_version: number }, ScrimBoard>(
  async (body, extras) => {
    try {
      const result = await postApiAdminScrimsIdBoardGenerate(api, props.id, body, extras)
      if (!result.board) throw new ApiError(0, "invalid_receipt", "分队回执无效，请重试。")
      return orderedBoard(result.board, props.initial.order)
    } catch (error) {
      // Generation may deliberately retain its picked list after an algorithm
      // validation failure. Use the returned version before another attempt.
      if (error instanceof ApiError) {
        const current = boardFromCurrent(error.current)
        if (current && !save.controller.dirty()) {
          const ordered = orderedBoard(current, props.initial.order)
          board.value = ordered
          save.controller.reset(splitValues(ordered), ordered.board_version)
        }
      }
      throw error
    }
  },
  (result) => {
    board.value = result
    save.controller.reset(splitValues(result), result.board_version)
    warning.value = ""
    clipboardMessage.value = ""
  },
)
const { pending: generatePending, message: generateMessage, uncertain: generateUncertain } = generator
const selectedCount = computed(() => values.value.signup_ids.length)
const disabled = computed(() => generating.value || generatePending.value || generateUncertain.value || snapshot.value.loginRequired)
const copyAllowed = computed(() => !dirty.value && !pending.value && !disabled.value && board.value.has_teams && Boolean(board.value.copy_text))
const contactsVisible = computed(() => record(board.value)?.show_contacts === true || board.value.signups.some((signup) => signup.contacts !== undefined))
const showResults = computed(() => board.value.has_teams)
const generationAllowed = computed(() => selectedCount.value === board.value.needed && !disabled.value && !pending.value)

function pick(id: number, event: Event): void {
  if (disabled.value || !(event.target instanceof HTMLInputElement)) return
  const ids = new Set(values.value.signup_ids)
  if (event.target.checked) ids.add(id)
  else ids.delete(id)
  save.set("signup_ids", [...ids], "choice")
  warning.value = ""
  clipboardMessage.value = ""
}

function move(id: number, zone: string): void {
  if (disabled.value) return
  const result = moveSignup(board.value, values.value, id, zone)
  warning.value = result.message
  if (!result.message) {
    save.set("placements", result.values.placements, "choice")
    clipboardMessage.value = ""
  }
}

async function generate(): Promise<void> {
  if (!generationAllowed.value) return
  const clean = await save.flush()
  if (!clean || selectedCount.value !== board.value.needed) return
  generating.value = true
  try {
    await generator.submit({ signup_ids: [...values.value.signup_ids], base_board_version: snapshot.value.version })
  } finally {
    generating.value = false
  }
}

async function copy(): Promise<void> {
  if (!copyAllowed.value) return
  try {
    await navigator.clipboard.writeText(board.value.copy_text)
    clipboardMessage.value = "已复制分队文字。"
  } catch {
    clipboardMessage.value = "无法自动复制，请选中下面的文字复制。"
  }
}
</script>

<template>
  <section class="b-section">
    <dl class="b-kv">
      <dt>规格</dt><dd>{{ formatLabel(board.scrim?.format ?? '') }}（每队 {{ teamSize(board.scrim?.format ?? '') }} 人，共需 {{ board.needed }} 人）</dd>
      <dt>开始时间</dt><dd>{{ timestamp(board.scrim?.starts_at) }}</dd>
      <dt>报名人数</dt><dd>{{ board.signups.length }}</dd>
    </dl>
  </section>
  <AdminNotice v-if="board.teams_stale" message="分队有变化：保存分队之后有人取消报名或换了游戏 ID，请重新生成或手动调整。" kind="warn" />
  <AdminNotice v-for="(item, index) in board.warnings ?? []" :key="index" :message="item" kind="warn" />
  <SaveStatus :snapshot="snapshot" :dirty="dirty" :pending="pending" @retry="save.save()" />
  <AdminNotice v-if="warning" :message="warning" kind="warn" />
  <AdminNotice v-if="generateMessage" :message="generateMessage" kind="error" />
  <section class="b-form">
    <div class="c-panel__head">
      <h2 class="b-section__title">勾选上场</h2>
      <nav aria-label="排序" class="c-tabs">
        <RouterLink
          v-for="option in orderOptions"
          :key="option.value"
          :class="{ 'is-active': board.order === option.value }"
          :to="`/admin/scrims/${id}/split/?order=${option.value}`"
        >{{ option.label }}</RouterLink>
      </nav>
    </div>
    <form class="b-form" @submit.prevent="generate">
      <table class="c-table c-table--stack">
        <thead><tr><th scope="col">上场</th><th scope="col">昵称</th><th scope="col">游戏 ID</th><th scope="col">能打的位置与段位</th><th v-if="contactsVisible" scope="col">联系方式</th><th scope="col">报名时间</th></tr></thead>
        <tbody>
          <tr v-for="signup in board.signups" :key="signup.signup_id">
            <td>
              <label class="c-check">
                <input
                  type="checkbox"
                  :value="signup.signup_id"
                  :checked="values.signup_ids.includes(signup.signup_id)"
                  :disabled="disabled"
                  :aria-label="`让 ${signup.nickname} 上场`"
                  @change="pick(signup.signup_id, $event)"
                >
              </label>
            </td>
            <td data-label="昵称">{{ signup.nickname }}{{ record(signup)?.is_active === false ? '（账号已停用）' : '' }}</td>
            <td data-label="游戏 ID"><span class="b-mono">{{ signup.battletag }}</span></td>
            <td data-label="位置与段位">
              <template v-for="(role, index) in signup.roles" :key="role">{{ index ? ' · ' : '' }}<span class="split-role">{{ roleLabel(role) }} {{ signup.rank_text[role] || boardRank(signup.ratings[role]) }}</span></template>
            </td>
            <td v-if="contactsVisible" data-label="联系方式">{{ signup.contacts?.join('；') || '—' }}</td>
            <td data-label="报名时间">{{ shortTimestamp(signup.created_at) }}</td>
          </tr>
          <tr v-if="!board.signups.length"><td :colspan="contactsVisible ? 6 : 5">还没有人报名。</td></tr>
        </tbody>
      </table>
      <ul v-if="fields.signup_ids?.length" class="c-field__error" role="alert"><li v-for="error in fields.signup_ids" :key="error">{{ error }}</li></ul>
      <div class="b-formbar">
        <span>已选 <strong>{{ selectedCount }}</strong> / 需要 {{ board.needed }} 人</span>
        <span v-if="selectedCount !== board.needed" class="b-formbar__note">人数正好等于需要人数时才能生成分队。</span>
        <button type="submit" class="c-btn c-btn--primary" :disabled="!generationAllowed">{{ generating || generatePending ? '正在生成…' : '生成分队' }}</button>
        <button v-if="generateUncertain" type="button" class="c-btn c-btn--secondary" :disabled="generatePending" @click="generator.retry()">重试上次生成</button>
      </div>
    </form>
  </section>
  <template v-if="showResults">
    <SplitResults :board="board" :values="values" :disabled="disabled" @move="move" @warning="warning = $event" />
    <ul v-if="fields.placements?.length" class="c-field__error" role="alert"><li v-for="error in fields.placements" :key="error">{{ error }}</li></ul>
    <section class="b-section">
      <h2 class="b-section__title">复制结果</h2>
      <p class="b-sub">存好后复制文字跟着换。</p>
      <textarea class="split-copy" rows="12" readonly :value="dirty ? '' : board.copy_text" aria-label="分队文字" />
      <div class="b-actions">
        <button type="button" class="c-btn c-btn--primary" :disabled="!copyAllowed" @click="copy">复制文字</button>
        <RouterLink v-if="copyAllowed" class="c-btn c-btn--secondary" :to="`/admin/scrims/${id}/split/text/`" target="_blank" rel="noopener">查看纯文本</RouterLink>
      </div>
      <p v-if="clipboardMessage" role="status">{{ clipboardMessage }}</p>
    </section>
  </template>
</template>
