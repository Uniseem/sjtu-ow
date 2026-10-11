<script lang="ts">
import type { LoadCtx } from "../router"
import { loadPersonal } from "../personal"

export function load(ctx: LoadCtx) {
  return loadPersonal(ctx, "基本资料")
}
</script>

<script setup lang="ts">
import { computed, inject, onMounted, reactive, ref } from "vue"
import { useHead } from "@unhead/vue"
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CAutosave from "@sjtu-ow/ui/CAutosave.vue"
import PersonalLayout from "../components/PersonalLayout.vue"
import ProfileFields from "../components/ProfileFields.vue"
import AvatarPanel from "../components/AvatarPanel.vue"
import { useApi } from "../api"
import { useAutosave } from "../use-autosave"
import { profileValues, readProfileCurrent, requirePageData, usePersonalUser } from "../personal"
import type { PersonalPageData } from "../personal"
import { patchPersonalProfile, validVersion } from "../pending-api"

const data = requirePageData(inject<PersonalPageData>("page-data"))
const profile = reactive({ ...data.profile })
const api = useApi()
const user = usePersonalUser(profile)
const save = useAutosave({
  initial: profileValues(profile),
  together: [["main_role", "flex_roles"]],
  version: validVersion(profile.version) ? profile.version : 0,
  available: () => validVersion(profile.version),
  readCurrent: readProfileCurrent,
  transport: (body, key, signal) => patchPersonalProfile(api, body, { key, signal, unauthorized: "throw" }),
})
const person = computed(() => ({
  ...user,
  nickname: save.values.value.nickname,
  avatar_image_id: profile.avatar_image_id,
}))
const enhanced = ref(false)
onMounted(() => { enhanced.value = true })
const loginHref = "/accounts/login/?next=" + encodeURIComponent("/me/")

useHead({ title: "基本资料 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })

function avatarChanged(image: number | null): void {
  profile.avatar_image_id = image
}

function choose(changes: Partial<ReturnType<typeof profileValues>>): void {
  save.setMany(changes, "choice")
}
</script>

<template>
  <PersonalLayout title="基本资料" current="/me/" :profile="profile" :user="person">
    <template #actions>
      <a href="/submit/" class="c-btn c-btn--secondary"><CIcon name="pen" />我要投稿</a>
    </template>
    <AvatarPanel :profile="profile" :person="person" @changed="avatarChanged" />
    <section aria-labelledby="me-basic">
      <SectionHead title="资料" heading-id="me-basic" />
      <form
        method="post"
        action="/me/"
        class="c-form max-w-xl"
        data-autosave
        :aria-busy="save.pending.value || undefined"
        @submit.prevent="save.save"
      >
        <CAutosave
          class="contents"
          :state="save.snapshot.value.state"
          :message="save.snapshot.value.state === 'idle' && !save.dirty.value ? '改了就自动保存' : save.snapshot.value.message"
          :dirty="save.dirty.value"
          :pending="save.pending.value"
          :login-required="save.snapshot.value.loginRequired"
          :login-href="loginHref"
          @retry="save.save"
        />
        <ProfileFields
          :values="save.values.value"
          :fields="save.fields.value"
          :disabled="!validVersion(profile.version)"
          @text="(name, value) => save.set(name, value, 'text')"
          @choice="choose"
          @blur="save.flush"
        />

        <p v-if="!validVersion(profile.version)" class="text-sm text-fg-2" role="status">暂时无法保存，请稍后再试。</p>
        <div class="c-formbar" :hidden="enhanced">
          <button type="submit" class="c-btn c-btn--primary" data-autosave-button :hidden="enhanced" :disabled="save.pending.value">保存</button>
        </div>
      </form>
    </section>
  </PersonalLayout>
</template>
