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
const save = useAdminSave({ initial: { name: '', description: '', is_visible: false, sort_order: 0 }, version: 0, readCurrent: () => null,
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
      <div class="b-fieldset">
        <div class="c-field">
          <label for="new-group-name" class="c-field__label">名称</label>
          <input id="new-group-name" class="c-input" maxlength="80" :value="save.values.value.name" @input="save.set('name', value($event), 'text')" @blur="save.flush" />
          <p class="b-sub">名称空着的分组不显示在网站上。</p>
        </div>
        <div class="c-field">
          <label for="new-group-description" class="c-field__label">简介</label>
          <textarea id="new-group-description" class="c-input" :value="save.values.value.description" @input="save.set('description', value($event), 'text')" @blur="save.flush" />
        </div>
        <label class="c-check">
          <input type="checkbox" :checked="save.values.value.is_visible" @change="save.set('is_visible', ($event.target as HTMLInputElement).checked, 'choice')" />显示</label>
          <div class="c-field">
            <label for="new-group-order" class="c-field__label">排序</label>
            <input id="new-group-order" type="number" class="c-input" :value="save.values.value.sort_order" @change="save.set('sort_order', Number(value($event)), 'choice')" />
          </div>
        </div>
        <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
        <button class="c-btn c-btn--primary" :disabled="save.pending.value">保存</button>
      </form>
      <section class="b-section">
        <h2 class="b-section__title">组里的成员</h2>
        <p class="b-section__text">先填上面任意一项，分组建好以后就能在这里加人。</p>
      </section>
    </AdminPage>
</template>
