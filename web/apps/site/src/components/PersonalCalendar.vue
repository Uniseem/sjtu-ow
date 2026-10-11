<script setup lang="ts">
import { ref, watch } from "vue"
import { postApiMeCalendarRenew } from "@sjtu-ow/api"
import type { GetApiMeCalendarOut } from "@sjtu-ow/api"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import { calendarAddress } from "../personal-list-schema"

const props = defineProps<{ calendar: GetApiMeCalendarOut }>()
const api = useApi()
const current = ref(props.calendar)
const notice = ref("")
const renew = useMutation(
  (_body: Record<string, never>, extras) => postApiMeCalendarRenew(api, extras),
  (calendar) => {
    calendarAddress(calendar.url, calendar.webcal)
    current.value = calendar
    notice.value = "订阅地址已更换，旧地址已经失效，请在手机上重新订阅。"
  },
)
watch(() => props.calendar, (calendar) => { current.value = calendar })
</script>

<template>
  <section aria-labelledby="me-calendar" data-calendar>
    <SectionHead title="订阅到手机日历" heading-id="me-calendar" />
    <p class="text-fg-2">把你报名的内战和赛事放进手机日历，时间改了日历也会跟着变，提醒用日历自己的。</p>
    <p class="mt-4 flex flex-wrap gap-3">
      <a :href="current.webcal" class="c-btn c-btn--secondary"><CIcon name="calendar" />订阅到日历</a>
    </p>
    <p class="mt-3 text-sm text-fg-2">点不开的话，在日历里选「添加订阅日历」，填这个地址：</p>
    <p class="mt-1 break-all font-code text-sm" data-calendar-url>{{ current.url }}</p>
    <p class="mt-2 text-sm text-fg-3">这个地址只属于你，别发给别人：拿到的人能看到你报名的活动名、队名和时间。</p>
    <form method="post" action="/me/calendar/reset/" class="mt-3" @submit.prevent="renew.submit({})">
      <button type="submit" class="c-btn c-btn--quiet c-btn--sm" :disabled="!renew.canStart.value">换一个订阅地址</button>{{ ' ' }}
      <span class="text-sm text-fg-3">地址给了不该给的人时用；换了以后旧地址立刻失效，手机上要重新订阅。</span>
    </form>
    <CMutationError :message="renew.message.value" :uncertain="renew.uncertain.value" :pending="renew.pending.value" @retry="renew.retry" />
    <p v-if="notice" class="text-sm text-fg-2" role="status">{{ notice }}</p>
  </section>
</template>
