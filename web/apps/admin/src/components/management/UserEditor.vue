<script setup lang="ts">
import { computed, ref } from "vue"
import { patchApiAdminUsersIdRoles, postApiAdminUsersIdActivate, postApiAdminUsersIdDeactivate } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminSession } from "../../core/session"
import { useAdminAction } from "../../core/use-action"
import { useAdminSave } from "../../core/use-save"
import SaveStatus from "../SaveStatus.vue"
import ActionState from "./ActionState.vue"
import ConfirmAction from "./ConfirmAction.vue"
import { patchUser, getRoles, type UserBasics, type AdminUserDetailOut } from "../../pages/management/pending"
import { useResource } from "../../pages/management/use-resource"
const props = defineProps<{ data: AdminUserDetailOut }>()
const emit = defineEmits<{ changed: [] }>()
const api = useAdminApi()
const session = useAdminSession()
const person = props.data.user
if (!person) throw new Error("UserEditor requires a user")
const id = String(person.ID)
import { currentReader } from "../../pages/management/current-reader"
const initial: UserBasics = { nickname: person.Nickname, is_sjtu: person.IsSJTU }
const save = useAdminSave<UserBasics>({ initial, version: person.Version,
  readCurrent: currentReader(initial), transport: (body, key, signal) => patchUser(api, id, body, { key, signal }) })
const roles = ref([...props.data.roles])
const choices = useResource(() => id, signal => getRoles(api, { signal }))
const assignable = computed(() => choices.data.value?.groups.filter(group => group.assignable) ?? [])
const roleAction = useAdminAction<string[], Awaited<ReturnType<typeof patchApiAdminUsersIdRoles>>>(
  (body, extras) => patchApiAdminUsersIdRoles(api, id, { roles: body }, extras), result => { roles.value = result.roles; emit("changed") })
const reason = ref("")
const own = computed(() => props.data.own_account === true || session.user.value?.id === person.ID)
const deleted = computed(() => props.data.is_deleted !== false)
const active = useAdminAction<{ active: boolean; reason: string }, { result: string; message: string }>(
  (body, extras) => body.active ? postApiAdminUsersIdActivate(api, id, extras) : postApiAdminUsersIdDeactivate(api, id, { reason: body.reason }, extras), () => emit("changed"))
function value(event: Event) { return (event.target as HTMLInputElement).value }
function checked(event: Event) { return (event.target as HTMLInputElement).checked }
function changeRole(name: string, enabled: boolean) { roles.value = enabled ? [...new Set([...roles.value, name])] : roles.value.filter(role => role !== name); void saveRoles() }
async function saveRoles() { if (await save.flush()) await roleAction.submit([...roles.value]) }
</script>
<template>
  <form class="b-form" novalidate @submit.prevent="save.save">
    <div class="b-fieldset">
      <div class="c-field" :class="{ 'is-invalid': save.fields.value.nickname?.length }">
        <label class="c-field__label" for="user-nickname">昵称</label>
        <input id="user-nickname" class="c-input" maxlength="16" :value="save.values.value.nickname" @input="save.set('nickname', value($event), 'text')" @blur="save.flush" />
        <p v-for="error in save.fields.value.nickname" :key="error" class="c-field__error" role="alert">{{ error }}</p>
      </div>
      <label class="c-check">
        <input type="checkbox" :checked="save.values.value.is_sjtu" @change="save.set('is_sjtu', checked($event), 'choice')" />是否来自交大</label>
      </div>
      <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
      <div class="b-actions">
        <button type="submit" class="c-btn c-btn--primary" :disabled="save.pending.value">保存</button>
      </div>
    </form>
    <section class="b-section">
      <h2 class="b-section__title">角色</h2>
      <p class="b-sub">投稿者、交大用户、校外用户由系统维护。</p>
      <p v-if="choices.message.value" class="c-field__error" role="alert">{{ choices.message.value }}</p>
      <form @submit.prevent="saveRoles">
        <label v-for="role in assignable" :key="role.id" class="c-check">
          <input type="checkbox" :checked="roles.includes(role.name)" :disabled="!roleAction.canStart.value" @change="changeRole(role.name, checked($event))" />{{ role.label || role.name }}</label>
          <div class="b-actions">
            <button class="c-btn c-btn--secondary c-btn--sm" type="submit" :disabled="!roleAction.canStart.value || choices.pending.value">保存角色</button>
          </div>
        </form>
        <ActionState :message="roleAction.message.value" :pending="roleAction.pending.value" :uncertain="roleAction.uncertain.value" @retry="roleAction.retry" />
      </section>
      <section v-if="!own" class="b-section">
        <h2 class="b-section__title">账号状态</h2>
        <template v-if="person.IsActive">
          <p class="b-sub">停用后不能再登录，待审批的入队申请会取消，当队长的战队会暂停招募。</p>
          <label class="c-field__label" for="stop-reason">停用原因</label>
          <textarea id="stop-reason" v-model="reason" class="c-input" maxlength="200" />
          <ConfirmAction title="停用账号" message="停用这个账号？不能再登录，待审批的入队申请会取消，当队长的战队会暂停招募。" label="停用账号" danger :pending="!active.canStart.value || !reason.trim()" @confirm="active.submit({ active: false, reason })" />
        </template>
        <p v-else-if="deleted" class="b-section__text">{{ data.is_deleted === true ? '账号已注销：数据已匿名化，不能再启用。' : '账号停用状态尚未确认，请重新加载资料。' }}</p>
        <template v-else>
          <p class="b-section__text">账号已停用，不能登录。</p>
          <p>{{ person.DeactivationNote }}</p>
          <button class="c-btn c-btn--secondary c-btn--sm" :disabled="!active.canStart.value" @click="active.submit({ active: true, reason: '' })">重新启用</button>
        </template>
        <ActionState :message="active.message.value" :pending="active.pending.value" :uncertain="active.uncertain.value" @retry="active.retry" />
      </section>
</template>
