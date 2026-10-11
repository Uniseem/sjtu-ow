<script setup lang="ts">
import CField from "@sjtu-ow/ui/CField.vue"
import { PLAY_ROLES, parseRank, rankChoices, rankValue } from "../personal"
import type { GameValues } from "../pending-api"

withDefaults(defineProps<{
  battletag: string
  values: GameValues
  fields: Record<string, string[]>
  editing?: boolean
  disabled?: boolean
  prefix?: string
}>(), { editing: false, disabled: false, prefix: "id" })

const emit = defineEmits<{
  battletag: [value: string]
  rank: [name: keyof GameValues, value: number | null]
  blur: []
}>()

const choices = rankChoices()
const rankFields = {
  tank: "rank_tank",
  damage: "rank_damage",
  support: "rank_support",
} as const

function rankInput(event: Event): number | null {
  return parseRank((event.target as HTMLSelectElement).value)
}
</script>

<template>
  <CField label="游戏 ID" :input-id="prefix + '_battletag'" required :errors="fields.battletag">
    <input
      :id="prefix + '_battletag'"
      :value="battletag"
      type="text"
      name="battletag"
      class="font-code"
      autocomplete="off"
      spellcheck="false"
      placeholder="名称#12345"
      maxlength="32"
      required
      :disabled="disabled"
      @input="emit('battletag', ($event.target as HTMLInputElement).value)"
      @blur="emit('blur')"
    >
  </CField>
  <CField
    v-for="role in PLAY_ROLES"
    :key="role.value"
    :label="role.label + '段位'"
    :input-id="prefix + '_' + rankFields[role.value]"
    :errors="fields[rankFields[role.value]]"
  >
    <select
      :id="prefix + '_' + rankFields[role.value]"
      :name="rankFields[role.value]"
      :value="rankValue(values[rankFields[role.value]])"
      :disabled="disabled"
      @change="emit('rank', rankFields[role.value], rankInput($event))"
    >
      <option v-for="choice in choices" :key="choice.value" :value="choice.value">{{ choice.label }}</option>
    </select>
  </CField>
</template>
