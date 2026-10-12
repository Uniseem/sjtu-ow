<script setup lang="ts">
import CField from "@sjtu-ow/ui/CField.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import type { SaveFields } from "@sjtu-ow/shared/autosave"
import { TEAM_ROLES } from "../team-domain"
const props=defineProps<{ accounts: Array<{id:number;battletag:string}>; accountId:number|null;roles:string[];fields:SaveFields;disabled?:boolean; roleQueue?:boolean; prefix:string }>()
const emit=defineEmits<{ account:[id:number|null];roles:[roles:string[]] }>()
function select(event:Event):void {const id=Number((event.target as HTMLSelectElement).value);emit("account",Number.isSafeInteger(id)&&id>0?id:null)}
function toggle(code:string,event:Event):void{const selected=new Set(props.roles);if((event.target as HTMLInputElement).checked)selected.add(code);else selected.delete(code);emit("roles",TEAM_ROLES.filter(role=>selected.has(role.code)).map(role=>role.code))}
</script>
<template>
  <CField label="游戏 ID" :input-id="prefix + '-account'" :errors="fields.game_account_id" required>
    <select :id="prefix + '-account'" name="game_account" :value="accountId || ''" required :disabled="disabled" @change="select"><option v-for="account in accounts" :key="account.id" :value="account.id">{{ account.battletag }}</option></select>
  </CField>
  <fieldset class="c-field" :disabled="disabled">
    <legend class="c-field__label mb-2">能打的位置（至少一个）</legend>
    <div class="c-choices"><label v-for="role in TEAM_ROLES" :key="role.code" class="c-choice"><input type="checkbox" name="roles" :value="role.code" :checked="roles.includes(role.code)" @change="toggle(role.code,$event)"><CIcon :name="'role-' + role.code" class="size-4" /><span>{{ role.label }}</span></label></div>
    <p class="c-field__help">{{ roleQueue?'角色限定内战：勾选的每个位置都要在这个游戏 ID 上填了段位。':'不限位置内战：这个游戏 ID 至少填了一个位置的段位即可。' }}</p>
    <p v-for="(error,index) in fields.roles" :key="index" class="c-field__error">{{ error }}</p>
  </fieldset>
</template>
