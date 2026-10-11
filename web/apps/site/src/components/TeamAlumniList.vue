<script setup lang="ts">
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"
import TeamAlumnusItem from "./TeamAlumnusItem.vue"
import type { TeamAlumnus } from "../team-domain"
defineProps<{alumni:TeamAlumnus[]}>()
</script>
<template>
  <section v-if="alumni.length" aria-labelledby="team-alumni" data-team-alumni>
    <SectionHead title="退役成员" heading-id="team-alumni" />
    <ul class="c-alumni"><TeamAlumnusItem v-for="record in alumni.slice(0,12)" :key="record.id" :record="record" /></ul>
    <details v-if="alumni.length>12" class="c-more"><summary>显示全部 <span class="font-numeric">{{ alumni.length }}</span> 人</summary><ul class="c-alumni"><TeamAlumnusItem v-for="record in alumni.slice(12)" :key="record.id" :record="record" /></ul></details>
  </section>
</template>
