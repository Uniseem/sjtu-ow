<script setup lang="ts">
import { postApiAdminSettingsTestEmail, patchApiAdminSettings, type CallExtras } from "@sjtu-ow/api"
import type { SaveRequest } from "@sjtu-ow/shared/autosave"
import { useAdminApi } from "../../core/api"
import { useAdminSave } from "../../core/use-save"
import { useAdminAction } from "../../core/use-action"
import { settingsSections, settingsValues, type Settings, type SettingsValues } from "../../pages/management/settings-fields"
import SaveStatus from "../SaveStatus.vue"
import ActionState from "./ActionState.vue"
import SecretEditor from "./SecretEditor.vue"
import SettingsImages from "./SettingsImages.vue"
const props = defineProps<{ settings: Settings }>()
const api = useAdminApi()
// The generated settings API supports versioned changed fields.
import { formReceipt } from "../../pages/management/save-projection"
async function patch(body: SaveRequest<SettingsValues>, extras: CallExtras) { return formReceipt(await patchApiAdminSettings(api, body, extras), initial) }
import { currentReader } from "../../pages/management/current-reader"
const initial = settingsValues(props.settings)
const save = useAdminSave({ initial, version: props.settings.version, readCurrent: currentReader(initial),
  transport: (body, key, signal) => patch(body, { key, signal }) })
const email = useAdminAction<null, Awaited<ReturnType<typeof postApiAdminSettingsTestEmail>>>((_, extras) => postApiAdminSettingsTestEmail(api, extras), result => { emailMessage.value = result.message })
import { ref } from "vue"
const emailMessage = ref("")
const sidePending=ref(false)
async function beforeSide(){if(sidePending.value)return false;if(!await save.flush())return false;sidePending.value=true;return true}
function sideChanged(settings:Settings){save.controller.reset(settingsValues(settings),settings.version)}
function sideSettled(){sidePending.value=false}
async function testEmail() { if (!sidePending.value && await save.flush()) { await email.submit(null) } }
function update(name: keyof SettingsValues, event: Event) {
  const input = event.target as HTMLInputElement
  if (typeof save.values.value[name] === 'boolean') save.set(name, input.checked as never, 'choice')
  else if (typeof save.values.value[name] === 'number') save.set(name, Number(input.value) as never, 'choice')
  else save.set(name, input.value as never, input.tagName === 'SELECT' ? 'choice' : 'text')
}
</script>
<template>
  <div class="b-split">
    <div class="b-form">
      <form class="b-form" novalidate @submit.prevent="save.save">
        <fieldset :disabled="sidePending" v-for="section in settingsSections" :key="section.title" class="b-fieldset">
          <legend class="b-fieldset__legend">{{ section.title }}</legend>
          <div v-for="field in section.fields" :key="field.name" class="c-field" :class="{ 'is-invalid': save.fields.value[field.name]?.length }">
            <label v-if="field.kind !== 'checkbox'" class="c-field__label" :for="`setting-${field.name}`">{{ field.label }}</label>
            <label v-if="field.kind === 'checkbox'" class="c-check">
              <input :id="`setting-${field.name}`" type="checkbox" :checked="Boolean(save.values.value[field.name])" @change="update(field.name, $event)" />{{ field.label }}</label>
              <textarea v-else-if="field.kind === 'textarea'" :id="`setting-${field.name}`" class="c-input" rows="4" :value="String(save.values.value[field.name])" @input="update(field.name, $event)" @blur="save.flush" />
              <select v-else-if="field.kind === 'select'" :id="`setting-${field.name}`" class="c-input" :value="save.values.value[field.name]" @change="update(field.name, $event)">
                <option v-for="choice in field.choices" :key="choice.value" :value="choice.value">{{ choice.label }}</option>
              </select>
              <input v-else :id="`setting-${field.name}`" class="c-input" :type="field.kind" :value="save.values.value[field.name]" :min="field.min" :max="field.max" @input="update(field.name, $event)" @blur="save.flush" />
              <p v-if="field.help" class="c-field__help">{{ field.help }}</p>
              <p v-for="error in save.fields.value[field.name]" :key="error" class="c-field__error" role="alert">{{ error }}</p>
            </div>
          </fieldset>
          <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
          <div class="b-formbar">
            <button class="c-btn c-btn--primary" :disabled="save.pending.value">保存</button>
            <span class="b-formbar__note">改了就自动保存；首页、横幅这些页面会跟着重新生成。</span>
          </div>
        </form>
        <SettingsImages :version="()=>save.snapshot.value.version" :settings="settings" :before-action="beforeSide" @changed="sideChanged" @settled="sideSettled" />
        <SecretEditor field="smtp_password" label="SMTP 密码" :present="settings.has_smtp_password" :before-action="beforeSide" @changed="sideChanged" @settled="sideSettled" />
        <SecretEditor field="moderation_api_key" label="接口密钥" :present="settings.has_moderation_api_key" :before-action="beforeSide" @changed="sideChanged" @settled="sideSettled" />
      </div>
      <aside class="b-aside">
        <section class="b-section">
          <h2 class="b-section__title">检查</h2>
          <button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="!email.canStart.value" @click="testEmail">发送测试邮件</button>
          <p class="b-sub">发给你自己的邮箱，用于检查 SMTP 配置。发送失败时会显示原因。</p>
          <p v-if="emailMessage" class="b-sub" role="status">{{ emailMessage }}</p>
          <ActionState :message="email.message.value" :pending="email.pending.value" :uncertain="email.uncertain.value" @retry="email.retry" />
        </section>
      </aside>
    </div>
</template>
