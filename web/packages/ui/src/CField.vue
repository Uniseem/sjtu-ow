<script setup lang="ts">
import CIcon from "./CIcon.vue"
withDefaults(defineProps<{
  label: string; inputId?: string; required?: boolean
  kind?: "control" | "checkbox" | "group"; errors?: string[]
}>(), { kind: "control", errors: () => [] })
</script>
<template>
  <fieldset v-if="kind === 'group'" :class="['c-field', { 'is-invalid': errors.length > 0 }]">
    <legend class="c-field__label mb-2">{{ label }}<span v-if="required" class="c-field__req" aria-hidden="true">*</span></legend>
    <slot />
    <div v-if="$slots.help" class="c-field__help"><slot name="help" /></div>
    <p v-if="errors.length" class="c-field__error" role="alert"><CIcon name="alert" /><span>{{ errors[0] }}</span></p>
  </fieldset>
  <div v-else :class="['c-field', { 'is-invalid': errors.length > 0 }]">
    <label v-if="kind === 'checkbox'" class="c-check" :for="inputId"><slot /><span>{{ label }}<span v-if="required" class="c-field__req" aria-hidden="true">*</span></span></label>
    <template v-else>
      <label class="c-field__label" :for="inputId">{{ label }}<span v-if="required" class="c-field__req" aria-hidden="true">*</span></label>
      <slot />
    </template>
    <div v-if="$slots.help" class="c-field__help"><slot name="help" /></div>
    <p v-if="errors.length" class="c-field__error" role="alert"><CIcon name="alert" /><span>{{ errors[0] }}</span></p>
  </div>
</template>
