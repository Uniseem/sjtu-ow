<script setup lang="ts">
import { computed } from "vue"
import MeLayout from "@sjtu-ow/ui/MeLayout.vue"
import { PERSONAL_NAV } from "../personal"
import type { AvatarPerson } from "@sjtu-ow/ui/types"
import type { PersonalProfile } from "../pending-api"

const props = defineProps<{
  title: string
  current: string
  profile: PersonalProfile
  user: AvatarPerson
}>()

// Prefer the server's exact missing-data projection. These two gaps have
// a direct equivalent in the old IsProfileComplete(game IDs, contacts) rule.
const gaps = computed(() => {
  if (props.profile.profile_gaps) return props.profile.profile_gaps
  const result: { label: string; href: string; hint: string }[] = []
  if (!props.profile.game_accounts.length) result.push({
    label: "游戏 ID",
    href: "/me/game-accounts/",
    hint: "至少绑定 1 个游戏 ID",
  })
  if (!props.profile.contacts.length) result.push({
    label: "联系方式",
    href: "/me/contacts/",
    hint: "至少填写 1 种联系方式",
  })
  return result
})
</script>

<template>
  <MeLayout
    :title="title"
    :current="current"
    :user="user"
    :nav="PERSONAL_NAV"
    :gaps="gaps"
    :waiting="profile.waiting_letters ?? 0"
  >
    <template #actions><slot name="actions" /></template>
    <slot />
  </MeLayout>
</template>
