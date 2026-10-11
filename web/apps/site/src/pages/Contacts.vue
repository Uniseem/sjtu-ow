<script lang="ts">
import type { LoadCtx } from "../router"
import { httpError } from "../router"
import { loadPersonal, personalId } from "../personal"

export async function load(ctx: LoadCtx) {
  const result = await loadPersonal(ctx, "联系方式")
  const editId = ctx.params.id ? personalId(ctx.params.id) : undefined
  if (editId && !result.profile.contacts.some((contact) => contact.id === editId)) throw httpError(404)
  return { ...result, newItem: ctx.query.new === "1" && !editId, editId }
}
</script>

<script setup lang="ts">
import { inject, reactive, ref, watch } from "vue"
import { useHead } from "@unhead/vue"
import { useRouter } from "vue-router"
import { deleteApiMeContactsId } from "@sjtu-ow/api"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import PersonalLayout from "../components/PersonalLayout.vue"
import ContactEditor from "../components/ContactEditor.vue"
import ContactCreate from "../components/ContactCreate.vue"
import { requirePageData, usePersonalUser } from "../personal"
import type { PersonalPageData } from "../personal"
import type { Contact } from "../pending-api"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"

const data = requirePageData(inject<PersonalPageData>("page-data"))
const profile = reactive({ ...data.profile, contacts: [...data.profile.contacts] })
const user = usePersonalUser(profile)
const api = useApi()
const router = useRouter()
const confirm = useConfirm()
const notice = ref("")
const newItem = ref(data.newItem === true)
const editId = ref(data.editId)
const deletingId = ref<number | null>(null)
const remove = useMutation(
  (id: number, extras) => deleteApiMeContactsId(api, id, extras),
  () => {
    profile.contacts = profile.contacts.filter((contact) => contact.id !== deletingId.value)
    notice.value = "联系方式已删除。"
  },
)

function removeContact(id: number): void {
  if (remove.pending.value || remove.uncertain.value) return
  if (!confirm("确定删除这个联系方式？")) return
  deletingId.value = id
  notice.value = ""
  void remove.submit(id)
}

function created(contact: Contact): void {
  profile.contacts.push(contact)
  newItem.value = false
  notice.value = "联系方式已添加。"
  void router.replace("/me/contacts/")
}

async function finished(): Promise<void> {
  editId.value = undefined
  await router.replace("/me/contacts/")
}

watch(() => data.profile, (next) => {
  Object.assign(profile, next, { contacts: [...next.contacts] })
  newItem.value = data.newItem === true
  editId.value = data.editId
})
watch(() => [data.newItem, data.editId], () => {
  newItem.value = data.newItem === true
  editId.value = data.editId
})

useHead({ title: "联系方式 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })
</script>

<template>
  <PersonalLayout title="联系方式" current="/me/contacts/" :profile="profile" :user="user">
    <CMutationError
      :message="remove.message.value"
      :uncertain="remove.uncertain.value"
      :pending="remove.pending.value"
      @retry="remove.retry"
    />
    <p v-if="notice" class="text-sm text-fg-2" role="status">{{ notice }}</p>
    <div id="contact-list" class="flex flex-col gap-4">
      <article v-for="contact in profile.contacts" :id="'contact-' + contact.id" :key="contact.id" class="c-panel">
        <ContactEditor v-if="editId === contact.id" :key="contact.id" :contact="contact" @done="finished" />
        <div v-else class="flex flex-wrap items-center justify-between gap-3">
          <p class="flex flex-wrap items-baseline gap-3">
            <span class="c-tag c-tag--strong">{{ contact.type_label }}</span>
            <span class="font-code text-lg">{{ contact.value }}</span>
          </p>
          <div class="flex flex-wrap gap-2">
            <a :href="'/me/contacts/' + contact.id + '/'" class="c-btn c-btn--secondary c-btn--sm">
              <CIcon name="edit" />编辑
            </a>
            <form
              method="post"
              :action="'/me/contacts/' + contact.id + '/delete/'"
              @submit.prevent="removeContact(contact.id)"
            >
              <button
                type="submit"
                class="c-btn c-btn--danger c-btn--sm"
                :disabled="remove.pending.value || remove.uncertain.value"
              ><CIcon name="trash" />删除</button>
            </form>
          </div>
        </div>
      </article>
      <CEmpty
        v-if="!profile.contacts.length"
        title="还没有联系方式"
        message="至少填写 1 种联系方式后才能报名赛事和内战。"
      />
      <div id="create-contact">
        <ContactCreate v-if="newItem" @created="created" />
      </div>
      <a href="/me/contacts/?new=1" class="c-btn c-btn--primary self-start">
        <CIcon name="plus" />新增联系方式
      </a>
    </div>
  </PersonalLayout>
</template>
