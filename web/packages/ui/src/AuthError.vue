<script setup lang="ts">
import CIcon from "./CIcon.vue"
defineProps<{ message?: string }>()
</script>
<template><p v-if="message" class="c-field__error" role="alert"><CIcon name="alert" /><span>{{ message }}</span></p></template>
