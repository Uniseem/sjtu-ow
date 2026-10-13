<script setup lang="ts">
import { computed, ref } from "vue"
import { patchApiAdminUsersIdRoles } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useAdminSave } from "../../core/use-save"
import SaveStatus from "../SaveStatus.vue"
import ActionState from "./ActionState.vue"
import { patchUser, getRoles, type UserBasics, type AdminUserDetailOut } from "../../pages/management/pending"
import { useResource } from "../../pages/management/use-resource"
const props = defineProps<{ data: AdminUserDetailOut }>()
const emit = defineEmits<{ changed: [] }>()
const api = useAdminApi()
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
function value(event: Event) { return (event.target as HTMLInputElement).value }
function checked(event: Event) { return (event.target as HTMLInputElement).checked }
function changeRole(name: string, enabled: boolean) { roles.value = enabled ? [...new Set([...roles.value, name])] : roles.value.filter(role => role !== name); void saveRoles() }
async function saveRoles() { if (await save.flush()) await roleAction.submit([...roles.value]) }
</script>
<template>
  <form class="b-form" novalidate @submit.prevent="saveRoles">
      <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
    <div class="b-fieldset">
      <div class="c-field" :class="{ 'is-invalid': save.fields.value.nickname?.length }">
        <label class="c-field__label" for="user-nickname">昵称<span class="c-field__req" aria-hidden="true">*</span></label>
        <input id="user-nickname" name="nickname" required minlength="2" class="c-input" maxlength="16" :value="save.values.value.nickname" @input="save.set('nickname', value($event), 'text')" @blur="save.flush" />
        <p v-for="error in save.fields.value.nickname" :key="error" class="c-field__error" role="alert">{{ error }}</p>
      </div>
      <div class="c-field"><label class="c-check">
        <input name="is_sjtu" type="checkbox" :checked="save.values.value.is_sjtu" @change="save.set('is_sjtu', checked($event), 'choice')" /><span>是否来自交大</span></label></div>
    <fieldset class="c-field">
      <legend class="c-field__label mb-2">角色</legend>

      <p v-if="choices.message.value" class="c-field__error" role="alert">{{ choices.message.value }}</p>

        <div><div v-for="role in assignable" :key="role.id"><label class="c-check">
          <input name="roles" :value="role.name" type="checkbox" :checked="roles.includes(role.name)" :disabled="!roleAction.canStart.value" @change="changeRole(role.name, checked($event))" />{{ role.label || role.name }}</label></div></div>
<p class="c-field__help">投稿者、交大用户、校外用户由系统按账号情况维护，不在这里改。</p>
        <ActionState :message="roleAction.message.value" :pending="roleAction.pending.value" :uncertain="roleAction.uncertain.value" @retry="roleAction.retry" />
      </fieldset>

      </div>

      <div class="b-actions" hidden>
        <button hidden type="submit" class="c-btn c-btn--primary" :disabled="save.pending.value">保存</button>
      </div>
    </form>

</template>
