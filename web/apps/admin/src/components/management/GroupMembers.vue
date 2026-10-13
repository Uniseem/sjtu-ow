<script setup lang="ts">
import { computed, onUnmounted, ref, shallowRef, watch } from "vue"
import { deleteApiAdminMemberGroupPeopleId, getApiAdminMemberGroupsIdPeople, postApiAdminMemberGroupPeopleIdMove, postApiAdminMemberGroupPeopleIdTitle, postApiAdminMemberGroupsIdPeople, type GetApiAdminMemberGroupsIdOut, type GetApiAdminMemberGroupsIdPeopleOut } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import CAvatar from "@sjtu-ow/ui/CAvatar.vue"
import ActionState from "./ActionState.vue"
import ConfirmAction from "./ConfirmAction.vue"
import GroupMemberTitle from "./GroupMemberTitle.vue"
const props = defineProps<{ id: number; initial: GetApiAdminMemberGroupsIdOut['members']; beforeAction: () => Promise<boolean> }>()
const api = useAdminApi()
const members = shallowRef([...props.initial])
import { useAdminSession } from "../../core/session"
const session = useAdminSession()
const search = ref("")
const submitted = ref("")
const results = shallowRef<GetApiAdminMemberGroupsIdPeopleOut['results']>([])
const searching = ref(false)
const searchError = ref("")
const available = computed(() => results.value.filter(result => !members.value.some(member => member.user_id === result.user_id)))
let flight: AbortController | undefined
let revision = 0
let timer: ReturnType<typeof setTimeout> | undefined
const action = useAdminAction<{ kind: 'add' | 'move' | 'remove'; id: number; step: number }, GetApiAdminMemberGroupsIdOut>(
  (body, extras) => body.kind === 'add' ? postApiAdminMemberGroupsIdPeople(api, props.id, { user_id: body.id }, extras) : body.kind === 'move' ? postApiAdminMemberGroupPeopleIdMove(api, body.id, { step: body.step }, extras) : deleteApiAdminMemberGroupPeopleId(api, body.id, extras),
  result => { members.value = result.members })
async function act(kind: 'add' | 'move' | 'remove', id: number, step = 0) { if (await props.beforeAction()) await action.submit({ kind, id, step }) }
async function find() {
  if (timer) { clearTimeout(timer); timer = undefined }
  const current = ++revision
  flight?.abort()
  flight = new AbortController()
  submitted.value = search.value.trim()
  searchError.value = ""
  results.value = []
  if (!submitted.value) { searching.value = false; return }
  searching.value = true
  try {
    const response = await getApiAdminMemberGroupsIdPeople(api, props.id, { q: submitted.value }, { signal: flight.signal })
    if (current === revision) results.value = response.results.slice(0, 10)
  } catch (error) {
    if (current === revision) searchError.value = error instanceof Error ? error.message : '暂时无法搜索。'
  } finally { if (current === revision) searching.value = false }
}
function updateMembers(next: GetApiAdminMemberGroupsIdOut) { members.value = next.members }
watch(search, () => {
 if (timer) clearTimeout(timer)
 revision++; flight?.abort(); searching.value = false
 timer = setTimeout(() => { void find() }, 250)
})
onUnmounted(() => { revision++; flight?.abort(); if (timer) clearTimeout(timer) })
</script>
<template>
  <section class="b-section" data-memberships>
    <h2 class="b-section__title">组里的成员（{{ members.length }} 人）</h2>
    <p class="b-section__text">按这个顺序显示在成员展示页上。只能加已加入的用户（没停用、验证过邮箱）。职务可以不填，多个职务用顿号分开，每个最多 10 字，改了就存。</p>
    <form class="b-filters" role="search" @submit.prevent="find">
      <input v-model="search" name="q" type="search" class="c-input" autocomplete="off" :placeholder="session.user.value?.superuser ? '搜昵称或邮箱，加进这个分组' : '搜昵称，加进这个分组'" :aria-label="session.user.value?.superuser ? '搜昵称或邮箱' : '搜昵称'" />
      <button class="c-btn c-btn--secondary c-btn--sm" :disabled="searching">搜索</button>
    </form>
    <p v-if="searching" class="b-sub" role="status">正在搜索…</p>
    <p v-if="searchError" class="c-field__error" role="alert">{{ searchError }}</p>
    <ul class="b-list" aria-live="polite">
      <li v-for="person in available" :key="person.user_id">
        <span>{{ person.nickname }}<span class="b-sub">{{ person.email || `#${person.user_id}` }}</span>
      </span>
      <form @submit.prevent="act('add', person.user_id)"><button type="submit" class="c-btn c-btn--secondary c-btn--sm" :disabled="!action.canStart.value">加入</button></form>
    </li>
    <li v-if="submitted && !searching && !searchError && !available.length">
      <span>没有找到「{{ submitted }}」：只列已加入、还不在组里的人。</span>
    </li>
  </ul>
  <ol v-if="members.length" class="b-list b-people">
    <li v-for="(row, index) in members" :key="row.id" :data-membership="row.id">
      <span class="b-people__who"><CAvatar :person="{ id: row.user_id, nickname: row.nickname, avatar_image_id: row.avatar_image_id, default_avatar_image_id: row.default_avatar_image_id, is_active: row.is_active }" size="xs" />
        <span>{{ row.nickname }}<span class="b-sub">{{ row.email || `#${row.user_id}` }}</span>
      </span>
    </span>
    <GroupMemberTitle :key="`${row.id}:${row.title}`" :member="row" @changed="updateMembers" />
    <span class="b-rowacts">
      <form @submit.prevent="act('move', row.id, -1)"><button type="submit" class="c-btn c-btn--quiet c-btn--sm" :disabled="index === 0 || !action.canStart.value">上移</button></form>
      <form @submit.prevent="act('move', row.id, 1)"><button type="submit" class="c-btn c-btn--quiet c-btn--sm" :disabled="index === members.length - 1 || !action.canStart.value">下移</button></form>
      <ConfirmAction title="移出分组" :message="`把「${row.nickname}」移出这个分组？`" label="移出" danger :pending="!action.canStart.value" @confirm="act('remove', row.id)" />
    </span>
  </li>
  </ol>
  <p v-else class="b-section__text">组里还没有人，用上面的搜索框加。</p>
  <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
  </section>
</template>
