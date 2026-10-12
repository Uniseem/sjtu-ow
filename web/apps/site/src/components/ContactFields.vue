<script setup lang="ts">
import CField from "@sjtu-ow/ui/CField.vue"
import { CONTACT_TYPES } from "../personal"
import type { ContactValues } from "../pending-api"

withDefaults(defineProps<{
  values: ContactValues
  fields: Record<string, string[]>
  disabled?: boolean
  prefix?: string
}>(), { disabled: false, prefix: "id" })

defineEmits<{
  type: [value: string]
  value: [value: string]
  blur: []
}>()
</script>

<template>
  <CField label="类型" :input-id="prefix + '_type'" required :errors="fields.type">
    <select
      :id="prefix + '_type'"
      :value="values.type"
      name="type"
      required
      :disabled="disabled"
      @change="$emit('type', ($event.target as HTMLSelectElement).value)"
    >
      <option value="" :selected="!values.type">---------</option>
      <option v-for="type in CONTACT_TYPES" :key="type.value" :value="type.value" :selected="values.type === type.value">{{ type.label }}</option>
    </select>
  </CField>
  <CField label="内容" :input-id="prefix + '_value'" required :errors="fields.value">
    <input
      :id="prefix + '_value'"
      :value="values.value"
      type="text"
      name="value"
      maxlength="64"
      required
      :disabled="disabled"
      @input="$emit('value', ($event.target as HTMLInputElement).value)"
      @blur="$emit('blur')"
    >
  </CField>
</template>
