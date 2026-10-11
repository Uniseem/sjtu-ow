<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiLetters } from "@sjtu-ow/api"
import { readWaitingLetters } from "../letter-schema"

export async function load(ctx: LoadCtx) {
  return { title: "还没发的信", waiting: readWaitingLetters(await getApiLetters(ctx.api)) }
}
</script>

<script setup lang="ts">
import { inject } from "vue"
import { useHead } from "@unhead/vue"
import type { GetApiLettersOut } from "@sjtu-ow/api"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import LettersLayout from "../components/LettersLayout.vue"
import { requirePageData } from "../personal"
import { letterDate, waitingURL } from "../letters"

const data = requirePageData(inject<{ waiting: GetApiLettersOut }>("page-data"))
useHead({ title: "还没发的信 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })
</script>

<template>
  <LettersLayout title="还没发的信" heading="还没发的信" lede="做完事以后没决定发不发的信。等满 7 天作废。">
    <ul v-if="data.waiting.batches.length" class="flex flex-col gap-4" data-held-batches>
      <li
        v-for="item in data.waiting.batches"
        :key="item.batch"
        class="c-panel flex flex-wrap items-center justify-between gap-3"
      >
        <div class="min-w-0">
          <p class="font-semibold">{{ item.subjects.join('；') }}</p>
          <p class="text-sm text-fg-2">{{ letterDate(item.at) }} · {{ item.people }} 人</p>
        </div>
        <a class="c-btn c-btn--secondary" :href="waitingURL(item.batch, item.in_back_office)">看信</a>
      </li>
    </ul>
    <CEmpty v-else title="没有等着发的信" message="做完事要发的信都处理过了。" />
  </LettersLayout>
</template>
