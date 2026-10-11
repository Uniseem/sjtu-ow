<script setup lang="ts">
withDefaults(defineProps<{
  name: string
  label: string
  errors?: string[]
  hint?: string
  required?: boolean
}>(), { errors: () => [], hint: "", required: false })
</script>
<template>
  <div class="c-field" :class="{ 'is-invalid': errors.length > 0 }">
    <label class="c-field__label" :for="name">
      {{ label }}<span v-if="required" aria-hidden="true"> *</span>
    </label>
    <slot :id="name" :describedby="errors.length ? `${name}-error` : hint ? `${name}-hint` : undefined" />
    <p v-if="hint" :id="`${name}-hint`" class="c-field__help">{{ hint }}</p>
    <ul v-if="errors.length" :id="`${name}-error`" class="c-field__error" role="alert">
      <li v-for="message in errors" :key="message">{{ message }}</li>
    </ul>
  </div>
</template>
