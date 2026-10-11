<script setup lang="ts">
import { computed } from "vue"
import { useAdminApi } from "../../core/api"
import { useAdminSave } from "../../core/use-save"
import { primitiveValues, readSaveReceipt } from "@sjtu-ow/shared/save-receipt"
import { readContentCurrent } from "../../pages/content/save-values"
import { renameCollection, type CollectionNode } from "../../pages/content/pending"
import SaveStatus from "../SaveStatus.vue"
const props = defineProps<{ node: CollectionNode; path: string }>()
const api = useAdminApi()
const emit = defineEmits<{ saved: [version: number, name: string] }>()
const shape = { name: props.node.name }
const save = useAdminSave({
  initial: shape,
  version: props.node.version,
  available: () => props.node.can_change,
  readCurrent: (value) => readContentCurrent(value, shape),
  transport: async (body, key, signal) => {
    const receipt = readSaveReceipt(await renameCollection(api, props.node.id, body, {
      key, signal, unauthorized: "throw",
    }), shape, primitiveValues(shape))
    if (receipt.saved.includes("name")) emit("saved", receipt.version, receipt.values?.name ?? body.changes.name ?? shape.name)
    return receipt
  },
})
const name = computed(() => save.values.value.name)
function input(event: Event): void {
  if (event.target instanceof HTMLInputElement) save.set("name", event.target.value)
}
</script>
<template>
  <form class="b-filters" @submit.prevent="save.save">
    <input type="text" name="name" class="c-input" :value="name" maxlength="255" :aria-label="`集合名称（改了就存）：${path}`" :disabled="!node.can_change" :aria-invalid="Boolean(save.fields.value.name?.length)" @input="input">
    <button class="c-btn c-btn--quiet c-btn--sm" :disabled="!node.can_change || save.pending.value">改名</button>
    <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
  </form>
</template>
