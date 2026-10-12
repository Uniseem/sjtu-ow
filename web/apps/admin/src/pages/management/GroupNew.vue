<script setup lang="ts">
import { watch } from "vue"
import { useRouter } from "vue-router"
import { postApiAdminMemberGroups, patchApiAdminMemberGroupsId } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminSave } from "../../core/use-save"
import AdminPage from "../../components/AdminPage.vue"
import SaveStatus from "../../components/SaveStatus.vue"
const api = useAdminApi()
const router = useRouter()
let id: number | null = null
let firstVersion: number | null = null
let creationKey: string | null = null
const save = useAdminSave({ initial: { name: '', description: '', is_visible: true, sort_order: 0 }, version: 0, readCurrent: () => null,
  transport: async (body, key, signal) => {
    if (id === null) {
      creationKey ??= crypto.randomUUID()
      const created = await postApiAdminMemberGroups(api, { key: creationKey, signal, unauthorized: 'throw' })
      if (!created.group) throw new Error('暂时无法建立分组。')
      id = created.group.id
      firstVersion = created.group.version
    }
    const response = await patchApiAdminMemberGroupsId(api, id, { ...body, base_version: firstVersion ?? body.base_version }, { key, signal, unauthorized: 'throw' })
    firstVersion = null
    return response
  } })
watch(() => save.snapshot.value.state, state => { if (state === 'saved' && !save.dirty.value && id !== null) void router.replace(`/admin/member-groups/${id}/`) })
function value(event: Event) { return (event.target as HTMLInputElement).value }
</script>
<template>
  <AdminPage title="新建分组" section="成员" back-href="/admin/member-groups/">
    <form class="b-form" @submit.prevent="save.save">
      <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
      <div class="b-fieldset">
        <div class="c-field">
          <label for="new-group-name" class="c-field__label">名称</label>
          <input id="new-group-name" name="name" class="c-input" maxlength="20" :value="save.values.value.name" @input="save.set('name', value($event), 'text')" @blur="save.flush" />
          <p class="c-field__help">名称空着时成员展示页上不出现这个分组。</p>
        </div>
        <div class="c-field">
          <label for="new-group-description" class="c-field__label">简介</label>
          <input type="text" id="new-group-description" name="description" class="c-input" maxlength="200" :value="save.values.value.description" @input="save.set('description', value($event), 'text')" @blur="save.flush" />
        </div>
        <label class="c-check">
          <input name="is_visible" type="checkbox" :checked="save.values.value.is_visible" @change="save.set('is_visible', ($event.target as HTMLInputElement).checked, 'choice')" />显示</label><p class="c-field__help">不显示的分组不出现在成员展示页上，组里的人仍然在「全部成员」里。</p>
          <div class="c-field">
            <label for="new-group-order" class="c-field__label">排序<span class="c-field__req" aria-hidden="true">*</span></label>
            <input id="new-group-order" name="sort_order" type="number" required min="0" max="32767" class="c-input" :value="save.values.value.sort_order" @change="save.set('sort_order', Number(value($event)), 'choice')" /><p class="c-field__help">数字小的排在前面。</p>
          </div>
        </div>

        <div class="b-formbar" hidden><button hidden class="c-btn c-btn--primary" :disabled="save.pending.value">保存</button></div>
      </form>
      <section class="b-section">
        <h2 class="b-section__title">组里的成员</h2>
        <p class="b-section__text">先填上面任意一项，分组建好以后就能在这里加人。</p>
      </section>
    </AdminPage>
</template>
