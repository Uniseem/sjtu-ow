<script setup lang="ts">
import { useHead } from "@unhead/vue";
import { ref } from "vue";
import { RouterLink } from "vue-router";
import type { HomeData } from "../api";
import { showTime } from "../shared-time";

const props = defineProps<{ data: HomeData }>();
useHead({ title: props.data.title, meta: [{ name: "description", content: "SJTU-OW SSR experiment" }] });
const clicks = ref(0);
</script>

<template>
  <section>
    <h1>{{ data.title }}</h1>
    <p>服务器渲染的时间：<time>{{ showTime(data.now) }}</time></p>
    <p><button type="button" data-test="counter" @click="clicks++">点了 {{ clicks }} 次</button></p>
    <ul class="teams">
      <li v-for="team in data.teams" :key="team.id">
        <RouterLink :to="`/teams/${team.id}/`">{{ team.name }}</RouterLink>
        <div>{{ team.members }} 人 · {{ showTime(team.founded) }}</div>
      </li>
    </ul>
  </section>
</template>
