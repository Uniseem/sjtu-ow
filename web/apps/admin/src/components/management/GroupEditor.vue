<script setup lang="ts">
import { useRouter } from "vue-router"
import { deleteApiAdminMemberGroupsId, patchApiAdminMemberGroupsId, type GetApiAdminMemberGroupsIdOut } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminSave } from "../../core/use-save"
import { useAdminAction } from "../../core/use-action"
import SaveStatus from "../SaveStatus.vue"
import ConfirmAction from "./ConfirmAction.vue"
import ActionState from "./ActionState.vue"
import GroupMembers from "./GroupMembers.vue"
const props = defineProps<{ data: GetApiAdminMemberGroupsIdOut }>()
const api = useAdminApi()
const router = useRouter()
const group = props.data.group
import { currentReader } from "../../pages/management/current-reader"
const initial = { name: group.name, description: group.description, is_visible: group.is_visible, sort_order: group.sort_order }
const save = useAdminSave({ initial, version: group.version, readCurrent: currentReader(initial),
  transport: (body, key, signal) => patchApiAdminMemberGroupsId(api, group.id, body, { key, signal }) })
const remove = useAdminAction<null, Awaited<ReturnType<typeof deleteApiAdminMemberGroupsId>>>((_, extras) => deleteApiAdminMemberGroupsId(api, group.id, extras), async () => { await router.push('/admin/member-groups/') })
function value(event: Event) { return (event.target as HTMLInputElement).value }
function checked(event: Event) { return (event.target as HTMLInputElement).checked }
async function deleteGroup() { if (await save.flush()) await remove.submit(null) }
</script>
<template>
  <div class="b-form">
    <form class="b-form" @submit.prevent="save.save">
      <div class="b-fieldset">
        <div class="c-field" :class="{ 'is-invalid': save.fields.value.name?.length }">
          <label for="group-name" class="c-field__label">名称</label>
          <input id="group-name" class="c-input" :value="save.values.value.name" maxlength="80" @input="save.set('name', value($event), 'text')" @blur="save.flush" />
          <p v-for="error in save.fields.value.name" :key="error" class="c-field__error" role="alert">{{ error }}</p>
          <p v-if="!save.values.value.name" class="b-sub">名称空着的分组不显示在网站上。</p>
        </div>
        <div class="c-field">
          <label for="group-description" class="c-field__label">简介</label>
          <textarea id="group-description" class="c-input" rows="4" :value="save.values.value.description" @input="save.set('description', value($event), 'text')" @blur="save.flush" />
        </div>
        <label class="c-check">
          <input type="checkbox" :checked="save.values.value.is_visible" @change="save.set('is_visible', checked($event), 'choice')" />显示</label>
          <div class="c-field">
            <label for="group-order" class="c-field__label">排序</label>
            <input id="group-order" class="c-input" type="number" :value="save.values.value.sort_order" @change="save.set('sort_order', Number(value($event)), 'choice')" />
            <p v-for="error in save.fields.value.sort_order" :key="error" class="c-field__error" role="alert">{{ error }}</p>
          </div>
        </div>
        <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
        <div class="b-formbar">
          <button type="submit" class="c-btn c-btn--primary" :disabled="save.pending.value">保存</button>
        </div>
      </form>
      <GroupMembers :id="group.id" :initial="data.members" :before-action="save.flush" />
      <ConfirmAction title="删除分组" :message="`删除分组「${save.values.value.name || '（未命名分组）'}」？组里的人不受影响。`" label="删除分组" danger :pending="!remove.canStart.value" @confirm="deleteGroup" />
      <ActionState :message="remove.message.value" :pending="remove.pending.value" :uncertain="remove.uncertain.value" @retry="remove.retry" />
    </div>
</template>
