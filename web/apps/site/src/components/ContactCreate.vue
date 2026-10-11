<script setup lang="ts">
import { reactive } from "vue"
import { postApiMeContacts } from "@sjtu-ow/api"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import ContactFields from "./ContactFields.vue"
import type { Contact, ContactValues } from "../pending-api"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"

const emit = defineEmits<{ created: [contact: Contact] }>()
const api = useApi()
const values = reactive<ContactValues>({ type: "qq", value: "" })
const mutation = useMutation(
  (body: ContactValues, extras) => postApiMeContacts(api, body, extras),
  (contact) => {
    emit("created", contact)
    values.value = ""
  },
)

function create(): void {
  void mutation.submit({ type: values.type, value: values.value.trim() })
}
</script>

<template>
  <form
    method="post"
    action="/me/contacts/"
    class="c-form"
    :aria-busy="mutation.pending.value || undefined"
    @submit.prevent="create"
  >
    <CMutationError
      :message="Object.keys(mutation.fields.value).length ? '' : mutation.message.value"
      :uncertain="mutation.uncertain.value"
      :pending="mutation.pending.value"
      @retry="mutation.retry"
    />
    <ContactFields
      :values="values"
      :fields="mutation.fields.value"
      :disabled="mutation.pending.value || mutation.uncertain.value"
      @type="values.type = $event"
      @value="values.value = $event"
    />
    <div class="flex flex-wrap gap-3">
      <button type="submit" class="c-btn c-btn--primary" :disabled="!mutation.canStart.value">添加</button>
      <a href="/me/contacts/" class="c-btn c-btn--quiet">取消</a>
    </div>
  </form>
</template>
