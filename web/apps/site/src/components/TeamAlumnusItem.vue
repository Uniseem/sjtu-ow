<script setup lang="ts">
import CAvatar from "@sjtu-ow/ui/CAvatar.vue"
import { joinedMonth,memberPerson,teamMemberHref,type TeamAlumnus } from "../team-domain"
defineProps<{record:TeamAlumnus}>()
</script>
<template>
  <li class="c-alumni__item" data-alumnus>
    <CAvatar :person="memberPerson(record)" size="sm" />
    <a v-if="teamMemberHref(record)" :href="teamMemberHref(record) || undefined" class="c-alumni__name" :title="record.nickname">{{ record.nickname }}</a>
    <span v-else class="c-alumni__name" :title="record.nickname">{{ record.nickname }}</span>
    <span class="c-alumni__when font-numeric"><time :datetime="record.joined_at">{{ joinedMonth(record.joined_at) }}</time> – <time :datetime="record.left_at">{{ joinedMonth(record.left_at) }}</time></span>
  </li>
</template>
