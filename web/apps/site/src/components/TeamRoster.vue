<script setup lang="ts">
import CAvatar from "@sjtu-ow/ui/CAvatar.vue"
import CPlay from "@sjtu-ow/ui/CPlay.vue"
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"
import { joinedMonth, memberPerson, memberPlay, teamMemberHref } from "../team-domain"
import type { TeamMember } from "../team-domain"

defineProps<{ members: TeamMember[] }>()
</script>

<template>
  <section aria-labelledby="team-roster">
    <SectionHead title="现役成员" heading-id="team-roster" />
    <ul v-if="members.length" class="c-squad">
      <li v-for="member in members" :key="member.user_id" class="c-squad__item" data-roster-member>
        <CAvatar :person="memberPerson(member)" size="md" />
        <div class="c-squad__main">
          <p class="c-squad__name">
            <a v-if="teamMemberHref(member)" :href="teamMemberHref(member) ?? undefined" class="truncate c-stretch" :title="member.nickname">{{ member.nickname }}</a>
            <span v-else class="truncate" :title="member.nickname">{{ member.nickname }}</span>
            <span v-if="member.role === 'captain'" class="c-tag c-tag--strong">队长</span>
            <span v-if="!member.is_active" class="c-tag" data-account-stopped>账号已停用</span>
          </p>
          <template v-if="member.is_active">
            <p v-if="member.motto" class="c-squad__motto" :title="member.motto">“{{ member.motto }}”</p>
            <CPlay :profile="memberPlay(member)" />
          </template>
          <p class="c-squad__meta"><time class="font-numeric" :datetime="member.joined_at">{{ joinedMonth(member.joined_at) }}</time> 入队</p>
        </div>
      </li>
    </ul>
    <p v-else class="text-fg-2">还没有成员。</p>
  </section>
</template>
