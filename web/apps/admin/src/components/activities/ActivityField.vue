<script setup lang="ts">
defineProps<{
  id: string
  label: string
  help?: string
  errors?: string[]
  required?: boolean
}>()
</script>

<template>
  <div class="c-field" :class="{ 'is-invalid': errors?.length }">
    <label class="c-field__label" :for="id">
      {{ label }}
      <span v-if="required" class="c-field__req" aria-hidden="true">*</span>
    </label>
    <slot :describedby="[help ? `${id}-help` : '', errors?.length ? `${id}-error` : ''].filter(Boolean).join(' ')" />
    <p v-if="help" :id="`${id}-help`" class="c-field__help">{{ help }}</p>
    <ul v-if="errors?.length" :id="`${id}-error`" class="c-field__error" role="alert">
      <li v-for="error in errors" :key="error">{{ error }}</li>
    </ul>
  </div>
</template>
