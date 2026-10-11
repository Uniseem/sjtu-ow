<script setup lang="ts">
import CAutosave from "@sjtu-ow/ui/CAutosave.vue"
import ContactFields from "./ContactFields.vue"
import { patchPersonalContact, validVersion } from "../pending-api"
import type { Contact, ContactValues } from "../pending-api"
import { readContactCurrent } from "../personal"
import { useApi } from "../api"
import { useAutosave } from "../use-autosave"

const props = defineProps<{ contact: Contact }>()
const emit = defineEmits<{ done: [] }>()
const api = useApi()
const initial: ContactValues = { type: props.contact.type, value: props.contact.value }
const save = useAutosave({
  initial,
  together: [["type", "value"]],
  version: validVersion(props.contact.version) ? props.contact.version : 0,
  available: () => validVersion(props.contact.version),
  readCurrent: readContactCurrent,
  transport: (body, key, signal) => patchPersonalContact(api, props.contact.id, body, { key, signal, unauthorized: "throw" }),
})

async function done(): Promise<void> {
  if (await save.save()) emit("done")
}

function changeType(type: string): void {
  save.set("type", type, "choice")
}
</script>

<template>
  <form
    method="post"
    :action="'/me/contacts/' + contact.id + '/'"
    class="c-form"
    data-autosave
    :aria-busy="save.pending.value || undefined"
    @submit.prevent="done"
  >
    <ContactFields
      :values="save.values.value"
      :fields="save.fields.value"
      :disabled="!validVersion(contact.version)"
      :prefix="'edit_' + contact.id"
      @type="changeType"
      @value="save.set('value', $event, 'text')"
      @blur="save.flush"
    />
    <CAutosave
      :state="save.snapshot.value.state"
      :message="save.snapshot.value.message"
      :dirty="save.dirty.value"
      :pending="save.pending.value"
      :login-required="save.snapshot.value.loginRequired"
      :login-href="'/accounts/login/?next=' + encodeURIComponent('/me/contacts/' + contact.id + '/')"
      @retry="save.save"
    />
    <p v-if="!validVersion(contact.version)" class="text-sm text-fg-2" role="status">暂时无法保存，请稍后再试。</p>
    <div class="flex flex-wrap gap-3">
      <button type="submit" class="c-btn c-btn--primary" :disabled="save.pending.value">完成</button>
    </div>
  </form>
</template>
