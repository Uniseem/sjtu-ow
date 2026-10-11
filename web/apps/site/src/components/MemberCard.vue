<script setup lang="ts">
import { computed } from "vue"
import { hue, initial } from "@sjtu-ow/shared/initial"
import { imageUrl } from "@sjtu-ow/shared/media"
import CPlay from "@sjtu-ow/ui/CPlay.vue"
import { memberPlay, type MemberCard } from "../member-domain"
const props = defineProps<{ member: MemberCard; titles: string[] }>()
const image = computed(() => props.member.avatar_image_id || props.member.default_avatar_image_id)
</script>
<template>
  <li class="c-person">
    <span :class="['c-person__pic', 'c-hue-' + hue(member.user_id)]" aria-hidden="true">
      <img v-if="image" :src="imageUrl(image, 'fill-400x400')" alt="" loading="lazy">
      <template v-else>{{ initial(member.nickname) }}</template>
    </span>
    <span class="c-person__body">
      <a :href="'/members/' + member.user_id + '/'" class="c-person__name c-stretch" :title="member.nickname">{{ member.nickname }}</a>
      <span v-if="titles.length" class="c-person__titles">
        <span v-for="(title, index) in titles.slice(0, 3)" :key="index" class="c-person__title">{{ title }}</span>
        <span v-if="titles.length > 3" class="c-person__more">+{{ titles.length - 3 }}</span>
      </span>
      <span v-if="member.motto" class="c-person__motto" :title="member.motto">“{{ member.motto }}”</span>
      <CPlay :profile="memberPlay(member)" />
      <span v-if="member.teams.length" class="c-person__meta">
        <template v-for="(team, index) in member.teams.slice(0, 2)" :key="team.id">
          <a :href="'/teams/' + team.id + '/'">{{ team.name }}</a><template v-if="index < Math.min(member.teams.length, 2) - 1">、</template>
        </template>
        <template v-if="member.teams.length > 2"> 等 <span class="font-numeric">{{ member.teams.length }}</span> 支战队</template>
      </span>
    </span>
  </li>
</template>
