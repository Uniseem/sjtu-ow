<script setup lang="ts">
import { computed, ref } from "vue"
import { patchApiAdminTeamsId, postApiAdminTeamsIdAssignCaptain, postApiAdminTeamsIdDisband } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminSave } from "../../core/use-save"
import { useAdminAction } from "../../core/use-action"
import SaveStatus from "../SaveStatus.vue"
import ConfirmAction from "./ConfirmAction.vue"
import ActionState from "./ActionState.vue"
import type { TeamAdminPage } from "../../pages/management/pending"
import { date } from "../../pages/management/format"
const props = defineProps<{ data: TeamAdminPage }>()
const emit = defineEmits<{ changed: [] }>()
const api = useAdminApi()
const team = props.data.team
if (!team) throw new Error("TeamEditor requires a team")
import { formReceipt } from "../../pages/management/save-projection"
import { currentReader } from "../../pages/management/current-reader"
const initial = { name: team.name, description: team.description, is_recruiting: team.is_recruiting, recruiting_roles: [...team.recruiting_roles] }
const save = useAdminSave({ initial, version: team.version, readCurrent: currentReader(initial),
  available: () => props.data.can_edit && !team.disbanded_at,
  transport: async (body, key, signal) => formReceipt(await patchApiAdminTeamsId(api, team.id, body, { key, signal }), initial) })
const captain = ref<number | null>(null)
const eligible = computed(() => props.data.members.filter(member => member.is_active && member.role !== "captain"))
const action = useAdminAction<{ kind: "captain" | "disband"; user: number }, { result: string }>(
  (body, extras) => body.kind === "captain" ? postApiAdminTeamsIdAssignCaptain(api, team.id, { user_id: body.user }, extras) : postApiAdminTeamsIdDisband(api, team.id, extras), () => emit("changed"))
function value(event: Event) { return (event.target as HTMLInputElement).value }
function checked(event: Event) { return (event.target as HTMLInputElement).checked }
function role(name: string, enabled: boolean) { save.set("recruiting_roles", enabled ? [...new Set([...save.values.value.recruiting_roles, name])] : save.values.value.recruiting_roles.filter(item => item !== name), "choice") }
async function act(kind: "captain" | "disband") { if (await save.flush()) await action.submit({ kind, user: captain.value ?? 0 }) }
</script>
<template>
  <div class="b-split">
    <form class="b-form" @submit.prevent="save.save">
      <fieldset class="b-fieldset" :disabled="!data.can_edit || Boolean(team.disbanded_at)">
        <div class="c-field" :class="{ 'is-invalid': save.fields.value.name?.length }">
          <label class="c-field__label" for="team-name">队名</label>
          <input id="team-name" class="c-input" :value="save.values.value.name" maxlength="80" @input="save.set('name', value($event), 'text')" @blur="save.flush" />
          <p v-for="message in save.fields.value.name" :key="message" class="c-field__error" role="alert">{{ message }}</p>
        </div>
        <div class="c-field">
          <label class="c-field__label" for="team-description">简介</label>
          <textarea id="team-description" class="c-input" rows="7" :value="save.values.value.description" @input="save.set('description', value($event), 'text')" @blur="save.flush" />
        </div>
        <label class="c-check">
          <input type="checkbox" :checked="save.values.value.is_recruiting" @change="save.set('is_recruiting', checked($event), 'choice')" />招募</label>
          <fieldset>
            <legend class="c-field__label">缺的位置</legend>
            <label v-for="position in [{ key: 'tank', label: '坦克' }, { key: 'damage', label: '输出' }, { key: 'support', label: '支援' }]" :key="position.key" class="c-check">
              <input type="checkbox" :checked="save.values.value.recruiting_roles.includes(position.key)" @change="role(position.key, checked($event))" />{{ position.label }}</label>
            </fieldset>
          </fieldset>
          <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
          <div class="b-formbar">
            <button type="submit" class="c-btn c-btn--primary" :disabled="!data.can_edit || Boolean(team.disbanded_at) || save.pending.value">保存</button>
          </div>
        </form>
        <aside class="b-aside">
          <section class="b-section">
            <h2 class="b-section__title">成员（{{ data.members.length }} 人）</h2>
            <ul class="b-list">
              <li v-for="member in data.members" :key="member.user_id">
                <RouterLink :to="`/admin/users/${member.user_id}/`">{{ member.nickname }}</RouterLink>
                <span class="b-sub">{{ member.role === 'captain' ? '队长' : '成员' }}{{ member.is_active ? '' : ' · 已停用' }}</span>
              </li>
            </ul>
            <p v-if="team.disbanded_at" class="b-sub">已解散 · {{ date(team.disbanded_at) }}</p>
          </section>
          <section v-if="data.can_assign_captain && !team.disbanded_at" class="b-section">
            <h2 class="b-section__title">指定队长</h2>
            <select v-model="captain" class="c-input" aria-label="新队长">
              <option :value="null">选择队员</option>
              <option v-for="member in eligible" :key="member.user_id" :value="member.user_id">{{ member.nickname }}</option>
            </select>
            <ConfirmAction title="指定队长" message="把战队交给这位成员？原队长将成为普通队员。" label="指定队长" :pending="!action.canStart.value || captain === null" @confirm="act('captain')" />
          </section>
          <section v-if="data.can_disband && !team.disbanded_at" class="b-section">
            <h2 class="b-section__title">解散</h2>
            <ConfirmAction title="解散战队" :message="`解散战队「${team.name}」？这个操作不能撤销。`" label="解散" danger :pending="!action.canStart.value" @confirm="act('disband')" />
          </section>
          <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
        </aside>
      </div>
</template>
