<script setup lang="ts">
import CField from "@sjtu-ow/ui/CField.vue"
import type { SaveFields } from "@sjtu-ow/shared/autosave"
import type { TeamValues } from "../team-editor"
import { TEAM_ROLES } from "../team-domain"
const props = defineProps<{ values: TeamValues; fields: SaveFields; disabled?: boolean; create?: boolean }>()
const emit = defineEmits<{ text: [name: "name" | "description" | "member_contact", value: string]; choice: [changes: Partial<TeamValues>]; blur: [] }>()
function input(event: Event): string { return (event.target as HTMLInputElement).value }
function role(code: string, event: Event): void {
  const selected = new Set(props.values.recruiting_roles)
  if ((event.target as HTMLInputElement).checked) selected.add(code)
  else selected.delete(code)
  emit("choice", { recruiting_roles: TEAM_ROLES.filter(role => selected.has(role.code)).map(role => role.code) })
}
</script>
<template>
  <CField label="队名" input-id="id_name" :errors="fields.name" required>
    <input id="id_name" :value="values.name" name="name" type="text" maxlength="16" minlength="2" required :disabled="disabled" aria-describedby="id_name_helptext" @input="emit('text', 'name', input($event))" @blur="emit('blur')">
    <template #help><span id="id_name_helptext">2 到 16 个字符，不能和现有战队重名。</span></template>
  </CField>
  <CField label="简介" input-id="id_description" :errors="fields.description">
    <textarea id="id_description" :value="values.description" name="description" rows="4" maxlength="500" :disabled="disabled" @input="emit('text', 'description', input($event))" @blur="emit('blur')" />
  </CField>
  <CField label="招募中" kind="checkbox" input-id="id_is_recruiting" :errors="fields.is_recruiting">
    <input id="id_is_recruiting" :checked="values.is_recruiting" name="is_recruiting" type="checkbox" :disabled="disabled" @change="emit('choice', { is_recruiting: ($event.target as HTMLInputElement).checked })">
  </CField>
  <CField label="缺的位置" kind="group" input-id="id_recruiting_roles" :errors="fields.recruiting_roles">
    <div id="id_recruiting_roles">
      <div v-for="(position, index) in TEAM_ROLES" :key="position.code">
        <label :for="`id_recruiting_roles_${index}`">
          <input
            :id="`id_recruiting_roles_${index}`"
            type="checkbox"
            name="recruiting_roles"
            :value="position.code"
            :checked="values.recruiting_roles.includes(position.code)"
            :disabled="disabled"
            aria-describedby="id_recruiting_roles_helptext"
            @change="role(position.code, $event)"
          >{{ position.label }}
        </label>
      </div>
    </div>
    <template #help><span id="id_recruiting_roles_helptext">招募中时显示在战队卡和战队主页上。都不勾表示哪个位置都要。</span></template>
  </CField>
  <CField v-if="!create" label="队内联系方式" input-id="id_member_contact" :errors="fields.member_contact">
    <input id="id_member_contact" :value="values.member_contact" name="member_contact" type="text" maxlength="100" :disabled="disabled" aria-describedby="id_member_contact_helptext" @input="emit('text', 'member_contact', input($event))" @blur="emit('blur')">
    <template #help><span id="id_member_contact_helptext">比如队伍 QQ 群号。只有本队成员看得到，入队通过的邮件里也会写上。</span></template>
  </CField>
</template>
