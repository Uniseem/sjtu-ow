<script setup lang="ts">
import { onUnmounted, ref } from "vue"
import { postApiAdminMemberGroupPeopleIdTitle, type GetApiAdminMemberGroupsIdOut } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import ActionState from "./ActionState.vue"
import { onBeforeRouteLeave, onBeforeRouteUpdate } from "vue-router"
const props = defineProps<{ member: GetApiAdminMemberGroupsIdOut['members'][number] }>()
const emit = defineEmits<{ changed: [value: GetApiAdminMemberGroupsIdOut] }>()
const api = useAdminApi()
const title = ref(props.member.title)
let committed = props.member.title
const saved = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined
const action = useAdminAction<string, GetApiAdminMemberGroupsIdOut>((body, extras) => postApiAdminMemberGroupPeopleIdTitle(api, props.member.id, { title: body }, extras), result => { committed = result.members.find(member => member.id === props.member.id)?.title ?? committed; saved.value = true; emit('changed', result) })
function schedule() { saved.value = false; if (timer) clearTimeout(timer); timer = setTimeout(() => { void submit() }, 800) }
async function submit() { if (timer) clearTimeout(timer); if (title.value !== committed && action.canStart.value) await action.submit(title.value) }
async function leave() {
  await submit()
  return !action.pending.value && !action.uncertain.value && title.value === committed
}
onBeforeRouteLeave(leave)
onBeforeRouteUpdate(leave)
onUnmounted(() => { if (timer) clearTimeout(timer) })
</script>
<template>
  <form class="b-people__title" @submit.prevent="submit">
    <p class="c-autosave" :data-state="action.pending.value ? 'saving' : action.message.value ? 'failed' : saved ? 'saved' : 'idle'" role="status" aria-live="polite">{{ action.pending.value ? '正在保存…' : action.message.value || (saved ? '已保存' : '') }}</p>
    <input v-model="title" name="title" class="c-input" maxlength="20" :aria-label="`${member.nickname}的职务`" placeholder="职务（可不填）" @input="schedule" @blur="submit" />
    <button hidden class="c-btn c-btn--quiet c-btn--sm" :disabled="!action.canStart.value">保存职务</button>
    <ActionState :message="''" :pending="false" :uncertain="action.uncertain.value" @retry="action.retry" />
  </form>
</template>
