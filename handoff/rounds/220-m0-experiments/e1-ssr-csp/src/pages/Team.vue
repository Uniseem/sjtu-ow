<script setup lang="ts">
import { useHead } from "@unhead/vue";
import type { TeamRow } from "../api";

const props = defineProps<{ data: TeamRow & { description: string } }>();
useHead({ title: `${props.data.name} - SJTU-OW`, meta: [{ property: "og:title", content: props.data.name }] });
</script>

<template>
  <article>
    <h1>{{ data.name }}</h1>
    <p>{{ data.description }}</p>
    <p><RouterLink to="/">回首页</RouterLink></p>
  </article>
</template>
