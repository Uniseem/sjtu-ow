<script setup lang="ts">
import { patchApiAdminTeamsId } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminSave } from "../../core/use-save"
import SaveStatus from "../SaveStatus.vue"
import ImageField from "../content/ImageField.vue"
import type { TeamAdminPage } from "../../pages/management/pending"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import { day } from "../../pages/management/format"
const props = defineProps<{ data: TeamAdminPage }>()
const api = useAdminApi()
const team = props.data.team
if (!team) throw new Error("TeamEditor requires a team")
import { formReceipt } from "../../pages/management/save-projection"
import { currentReader } from "../../pages/management/current-reader"
const initial = { logo_image_id: team.logo_image_id, name: team.name, description: team.description, is_recruiting: team.is_recruiting, recruiting_roles: [...team.recruiting_roles] }
const save = useAdminSave({ initial, version: team.version, readCurrent: currentReader(initial),
  available: () => props.data.can_edit && !team.disbanded_at,
  transport: async (body, key, signal) => {
    const clearing = Object.hasOwn(body.changes, "logo_image_id") && body.changes.logo_image_id === null
    const receipt = await patchApiAdminTeamsId(api, team.id, { ...body, changes: { ...body.changes, logo_image_id: body.changes.logo_image_id ?? undefined, ...(clearing ? { remove_logo: true } : {}) } }, { key, signal })
    return formReceipt({ ...receipt, saved: receipt.saved.map(name => name === "remove_logo" ? "logo_image_id" : name) }, initial)
  } })
function logo(id: number | null) { save.set("logo_image_id", id, "choice") }
function value(event: Event) { return (event.target as HTMLInputElement).value }
function checked(event: Event) { return (event.target as HTMLInputElement).checked }
function role(name: string, enabled: boolean) { save.set("recruiting_roles", enabled ? [...new Set([...save.values.value.recruiting_roles, name])] : save.values.value.recruiting_roles.filter(item => item !== name), "choice") }
</script>
<template>
  <div class="b-split">
    <form class="b-form" @submit.prevent="save.save">
      <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
      <fieldset class="b-fieldset" :disabled="!data.can_edit || Boolean(team.disbanded_at)">
        <div class="c-field" :class="{ 'is-invalid': save.fields.value.name?.length }">
          <label class="c-field__label" for="team-name">队名<span class="c-field__req" aria-hidden="true">*</span></label>
          <input id="team-name" name="name" required class="c-input" :value="save.values.value.name" maxlength="16" @input="save.set('name', value($event), 'text')" @blur="save.flush" />
          <p v-for="message in save.fields.value.name" :key="message" class="c-field__error" role="alert">{{ message }}</p>
        </div>
        <div class="c-field">
          <label class="c-field__label" for="team-description">简介</label>
          <textarea id="team-description" name="description" class="c-input" rows="10" maxlength="500" :value="save.values.value.description" @input="save.set('description', value($event), 'text')" @blur="save.flush" />
        </div>
        <div class="c-field"><label class="c-field__label">队标</label><ImageField :model-value="save.values.value.logo_image_id" name="logo" label="队标" :disabled="!data.can_edit || Boolean(team.disbanded_at)" @update:model-value="logo" /><p v-for="message in save.fields.value.logo_image_id" :key="message" class="c-field__error">{{ message }}</p></div>
        <label class="c-check">
          <input name="is_recruiting" type="checkbox" :checked="save.values.value.is_recruiting" @change="save.set('is_recruiting', checked($event), 'choice')" />招募中</label>
          <fieldset class="c-field">
            <legend class="c-field__label mb-2">缺的位置</legend>
            <label v-for="position in [{ key: 'tank', label: '坦克' }, { key: 'damage', label: '输出' }, { key: 'support', label: '支援' }]" :key="position.key" class="c-check">
              <input name="recruiting_roles" :value="position.key" type="checkbox" :checked="save.values.value.recruiting_roles.includes(position.key)" @change="role(position.key, checked($event))" />{{ position.label }}</label>
            <p class="c-field__help">招募中时显示在战队卡和战队主页上。都不勾表示哪个位置都要。</p></fieldset>
          </fieldset>

          <div class="b-actions" hidden>
            <button hidden type="submit" class="c-btn c-btn--primary" :disabled="!data.can_edit || Boolean(team.disbanded_at) || save.pending.value">保存</button>
          </div>
        </form>
        <aside class="b-aside">
          <section class="b-section">
            <h2 class="b-section__title">状态</h2>
            <dl class="b-kv"><dt>状态</dt><dd><CStatus :label="team.disbanded_at ? '已解散' : data.members.some(member => member.role === 'captain' && member.is_active) ? '正常' : '队长已停用'" :kind="team.disbanded_at ? 'off' : data.members.some(member => member.role === 'captain' && member.is_active) ? 'ok' : 'warn'" /></dd><dt>成立</dt><dd>{{ day(team.created_at) }}</dd><template v-if="team.disbanded_at"><dt>解散</dt><dd>{{ day(team.disbanded_at) }}</dd></template></dl>
            <a class="c-btn c-btn--secondary c-btn--sm" :href="`/teams/${team.id}/`" target="_blank" rel="noopener">战队主页<CIcon name="external" class="size-4" /></a>
            <div v-if="!team.disbanded_at" class="b-actions"><RouterLink v-if="data.can_assign_captain" class="c-btn c-btn--secondary c-btn--sm" :to="`/admin/teams/${team.id}/assign-captain/`">指定队长</RouterLink><RouterLink v-if="data.can_disband" class="c-btn c-btn--danger c-btn--sm" :to="`/admin/teams/${team.id}/disband/`">解散战队</RouterLink></div>
          </section>
          <section class="b-section"><h2 class="b-section__title">成员</h2><ul class="b-list"><li v-for="member in data.members" :key="member.user_id"><span>{{ member.nickname }}</span><span class="b-sub">{{ member.role === 'captain' ? '队长' : '队员' }}</span></li><li v-if="!data.members.length">没有成员</li></ul></section>
        </aside>
      </div>
</template>
