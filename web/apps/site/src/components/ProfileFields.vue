<script setup lang="ts">
import CField from "@sjtu-ow/ui/CField.vue"
import type { ProfileValues } from "../pending-api"
import { PLAY_ROLES, joinRoles, parseRoles } from "../personal"

const props = defineProps<{
  values: ProfileValues
  fields: Record<string, string[]>
  disabled?: boolean
}>()

const emit = defineEmits<{
  text: [name: "nickname" | "motto", value: string]
  choice: [changes: Partial<ProfileValues>]
  blur: []
}>()

function input(event: Event): string {
  return (event.target as HTMLInputElement).value
}

function toggleRole(role: string, event: Event): void {
  const checked = (event.target as HTMLInputElement).checked
  const selected = new Set(parseRoles(props.values.flex_roles))
  if (checked) selected.add(role)
  else selected.delete(role)
  emit("choice", { flex_roles: joinRoles([...selected]) })
}
</script>

<template>
  <CField label="昵称" input-id="id_nickname" required :errors="fields.nickname">
    <input
      id="id_nickname"
      :value="values.nickname"
      name="nickname"
      type="text"
      autocomplete="nickname"
      minlength="2"
      maxlength="16"
      required
      :disabled="disabled"
      @input="emit('text', 'nickname', input($event))"
      @blur="emit('blur')"
    >
  </CField>
  <CField label="是否来自上海交通大学" kind="group" required :errors="fields.is_sjtu">
    <div id="id_is_sjtu">
      <div>
        <label for="id_is_sjtu_0">
          <input
            id="id_is_sjtu_0"
            type="radio"
            name="is_sjtu"
            value="true"
            :checked="values.is_sjtu"
            :disabled="disabled"
            @change="emit('choice', { is_sjtu: true })"
          > 是
        </label>
      </div>
      <div>
        <label for="id_is_sjtu_1">
          <input
            id="id_is_sjtu_1"
            type="radio"
            name="is_sjtu"
            value="false"
            :checked="!values.is_sjtu"
            :disabled="disabled"
            @change="emit('choice', { is_sjtu: false })"
          > 否
        </label>
      </div>
    </div>
  </CField>
  <CField label="个人宣言" input-id="id_motto" :errors="fields.motto">
    <input
      id="id_motto"
      :value="values.motto"
      name="motto"
      type="text"
      maxlength="30"
      aria-describedby="id_motto_helptext"
      :disabled="disabled"
      @input="emit('text', 'motto', input($event))"
      @blur="emit('blur')"
    >
    <template #help>
      <span id="id_motto_helptext">一句话，最多 30 字，所有人都看得到；不能放链接。</span>
    </template>
  </CField>
  <CField label="主位置" kind="group" :errors="fields.main_role">
    <div id="id_main_role">
      <div>
        <label for="id_main_role_0">
          <input
            id="id_main_role_0"
            type="radio"
            name="main_role"
            value=""
            :checked="values.main_role === ''"
            :disabled="disabled"
            @change="emit('choice', { main_role: '' })"
          > 不填
        </label>
      </div>
      <div v-for="(role, index) in PLAY_ROLES" :key="role.value">
        <label :for="'id_main_role_' + (index + 1)">
          <input
            :id="'id_main_role_' + (index + 1)"
            type="radio"
            name="main_role"
            :value="role.value"
            :checked="values.main_role === role.value"
            :disabled="disabled"
            @change="emit('choice', { main_role: role.value })"
          > {{ role.label }}
        </label>
      </div>
    </div>
  </CField>
  <CField label="也能打" kind="group" :errors="fields.flex_roles">
    <div id="id_flex_roles">
      <div v-for="(role, index) in PLAY_ROLES" :key="role.value">
        <label :for="'id_flex_roles_' + index">
          <input
            :id="'id_flex_roles_' + index"
            type="checkbox"
            name="flex_roles"
            :value="role.value"
            :checked="parseRoles(values.flex_roles).includes(role.value)"
            :disabled="disabled"
            @change="toggleRole(role.value, $event)"
          > {{ role.label }}
        </label>
      </div>
    </div>
    <template #help>主位置以外还能打的位置。三个都选显示为「全能」。</template>
  </CField>
  <CField
    label="在成员展示和战队主页公开我的段位"
    kind="checkbox"
    input-id="id_show_rank"
    :errors="fields.show_rank"
  >
    <input
      id="id_show_rank"
      type="checkbox"
      name="show_rank"
      :checked="values.show_rank"
      :disabled="disabled"
      @change="emit('choice', { show_rank: ($event.target as HTMLInputElement).checked })"
    >
    <template #help>公开的是每个位置在你所有游戏 ID 里最高的段位，游戏 ID 本身不公开。</template>
  </CField>
</template>
