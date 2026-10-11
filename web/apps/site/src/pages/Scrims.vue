<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiScrims } from "@sjtu-ow/api"
export async function load(ctx: LoadCtx) { return { title:"内战",list:await getApiScrims(ctx.api) } }
</script>
<script setup lang="ts">
import { computed, inject } from "vue"
import { useHead } from "@unhead/vue"
import type { GetApiScrimsOut } from "@sjtu-ow/api"
import CPagehead from "@sjtu-ow/ui/CPagehead.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import CScrimRow from "@sjtu-ow/ui/CScrimRow.vue"
import { requirePageData } from "../personal"
import { eventDateTime } from "../event-domain"
const data=requirePageData(inject<{ list:GetApiScrimsOut }>("page-data"))
const upcoming=computed(()=>data.list.scrims.filter(scrim=>scrim.status!=="finished"))
const finished=computed(()=>data.list.scrims.filter(scrim=>scrim.status==="finished").reverse())
useHead({title:"内战 · SJTU-OW"})
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead c-pagehead--picture"><CPagehead section="scrims" :image-id="data.list.banner_image_id" /><div class="l-container l-container--narrow"><h1>内战</h1><p class="c-pagehead__lede">社团成员之间的对局。报名后管理员会统一分队，分队结果发到群里。</p></div></header>
    <div class="l-container l-container--narrow pt-10 pb-16 lg:pt-14 lg:pb-24">
      <div class="grid gap-14">
        <section v-if="upcoming.length" aria-labelledby="scrims-upcoming"><div class="c-sectionhead"><h2 id="scrims-upcoming">即将开始</h2></div><ol class="c-rows"><CScrimRow v-for="scrim in upcoming" :key="scrim.id" :scrim="{...scrim,starts_at:scrim.starts_at || ''}" :signups="scrim.signup_total" /></ol></section>
        <section v-if="finished.length" aria-labelledby="scrims-finished"><div class="c-sectionhead"><h2 id="scrims-finished">最近结束</h2></div>
          <table class="c-table c-table--stack"><thead><tr><th scope="col">内战</th><th scope="col">时间</th><th scope="col">规格</th><th scope="col" class="is-num">报名</th></tr></thead><tbody><tr v-for="scrim in finished" :key="scrim.id"><td data-label="内战"><a :href="'/scrims/' + scrim.id + '/'" class="font-semibold hover:text-primary-text">{{ scrim.title }}</a></td><td data-label="时间" class="font-numeric">{{ eventDateTime(scrim.starts_at) }}</td><td data-label="规格">{{ scrim.format_label }}</td><td data-label="报名" class="is-num font-numeric">{{ scrim.signup_total }} 人</td></tr></tbody></table>
        </section>
        <CEmpty v-if="!data.list.scrims.length" title="暂无内战" message="内战发布后会出现在这里。" />
      </div>
    </div>
  </main>
</template>
