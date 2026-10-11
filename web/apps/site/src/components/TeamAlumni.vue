<script setup lang="ts">
import { ref, watch } from "vue"
import { postApiTeamAlumniIdRemove } from "@sjtu-ow/api"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import { owDate } from "@sjtu-ow/shared/time"
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import type { PersonalAlumnus } from "../team-display"

const props = defineProps<{ records: PersonalAlumnus[] }>()
const api = useApi()
const confirm = useConfirm()
const records = ref([...props.records])
const removing = ref<number | null>(null)
const notice = ref("")
const mutation = useMutation(
  (id: number, extras) => postApiTeamAlumniIdRemove(api, id, extras),
  () => {
    records.value = records.value.filter((record) => record.id !== removing.value)
    notice.value = "已从退役名单去掉你的名字。"
  },
)

function remove(id: number): void {
  if (!mutation.canStart.value || !confirm("从这支战队的退役名单里去掉你的名字？")) return
  removing.value = id
  notice.value = ""
  void mutation.submit(id)
}

watch(() => props.records, (value) => { records.value = [...value] })
</script>

<template>
  <section v-if="records.length || notice" aria-labelledby="me-alumni" data-me-alumni>
    <SectionHead title="退役记录" heading-id="me-alumni" />
    <p class="mb-4 text-fg-2">离开的战队在战队主页的「退役成员」里列着你的名字和在队时间。不想被列出可以去掉。</p>
    <ul class="c-rows">
      <li v-for="record in records" :key="record.id" class="c-row c-row--plain">
        <div class="c-row__main">
          <p class="c-row__title"><a :href="'/teams/' + record.team_id + '/'">{{ record.team_name }}</a></p>
          <p class="c-row__meta font-numeric">{{ owDate(new Date(record.joined_at)) }} – {{ owDate(new Date(record.left_at)) }}</p>
        </div>
        <form method="post" :action="'/teams/' + record.team_id + '/alumni/' + record.id + '/remove/'" @submit.prevent="remove(record.id)">
          <input type="hidden" name="next" value="me">
          <button type="submit" class="c-btn c-btn--secondary c-btn--sm" :disabled="!mutation.canStart.value">从名单去掉</button>
        </form>
      </li>
    </ul>
    <CMutationError
      :message="mutation.message.value"
      :uncertain="mutation.uncertain.value"
      :pending="mutation.pending.value"
      @retry="mutation.retry"
    />
    <p v-if="notice" class="text-sm text-fg-2" role="status">{{ notice }}</p>
  </section>
</template>
