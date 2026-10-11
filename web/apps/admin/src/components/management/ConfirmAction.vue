<script setup lang="ts">
import { nextTick, ref, useId } from "vue"
const props = defineProps<{ title: string; message: string; label: string; pending?: boolean; danger?: boolean }>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()
const headingId = useId()
const dialog = ref<HTMLDialogElement | null>(null)
const opener = ref<HTMLButtonElement | null>(null)
async function open() { await nextTick(); dialog.value?.showModal() }
function cancel() { dialog.value?.close(); opener.value?.focus(); emit("cancel") }
function accept() { if (!props.pending) { dialog.value?.close(); emit("confirm") } }
</script>
<template>
  <button ref="opener" type="button" class="c-btn c-btn--secondary c-btn--sm" :class="{ 'is-danger': danger }" :disabled="pending" @click="open">{{ label }}</button>
  <dialog ref="dialog" class="b-dialog" :aria-labelledby="headingId" @cancel.prevent="cancel">
    <h2 :id="headingId" class="b-section__title">{{ title }}</h2>
    <p class="b-section__text">{{ message }}</p>
    <div class="b-actions">
      <button class="c-btn c-btn--primary" type="button" :disabled="pending" @click="accept">{{ label }}</button>
      <button class="c-btn c-btn--quiet" type="button" @click="cancel">取消</button>
    </div>
  </dialog>
</template>
