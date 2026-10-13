<script setup lang="ts">
import { postApiAdminSettingsTestEmail, patchApiAdminSettings, type CallExtras } from "@sjtu-ow/api"
import type { SaveRequest } from "@sjtu-ow/shared/autosave"
import { useAdminApi } from "../../core/api"
import { useAdminSave } from "../../core/use-save"
import { useAdminAction } from "../../core/use-action"
import { settingsSections, settingsValues, type Settings, type SettingsValues } from "../../pages/management/settings-fields"
import SaveStatus from "../SaveStatus.vue"
import ActionState from "./ActionState.vue"
import BackupEditor from "./BackupEditor.vue"
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
import { ref, computed } from "vue"
const orderedSections = computed(() => ["站点信息", "栏目横幅", "社区参数", "邮件发送", "AI 审核"].map(title => { const section = settingsSections.find(section => section.title === title); if (!section) return { title, fields: [] }; const orders: Record<string, string[]> = { "社区参数": ["team_max_members","team_max_captained","max_game_accounts","scrim_reminder_hours","tournament_reminder_hours"], "邮件发送": ["smtp_host","smtp_port","smtp_security","smtp_username","from_address","from_name","email_subject_prefix"], "AI 审核": ["moderation_enabled","moderation_base_url","moderation_model","moderation_notify_email","moderation_daily_limit","moderation_image_enabled","moderation_extra_params","moderation_timeout_seconds","moderation_max_tokens"] }; return { title, fields: [...section.fields].sort((a,b) => (orders[title]?.indexOf(a.name) ?? 0) - (orders[title]?.indexOf(b.name) ?? 0)) } }))
const emailMessage = ref("")
const fieldNames: Partial<Record<keyof SettingsValues, string>> = {
  moderation_notify_email: 'moderation_alert_email', moderation_extra_params: 'moderation_extra_body',
  moderation_timeout_seconds: 'moderation_timeout', moderation_max_tokens: 'moderation_max_output_tokens',
}
function fieldName(name: keyof SettingsValues) { return fieldNames[name] ?? name }
const backup = ref<InstanceType<typeof BackupEditor>|null>(null)
const sidePending=ref(false)
async function beforeSide(){if(sidePending.value)return false;sidePending.value=true;if(!await save.flush()){sidePending.value=false;return false}return true}
function sideChanged(settings:Settings){save.controller.reset(settingsValues(settings),settings.version)}
function sideSettled(){sidePending.value=false}
async function saveAll() { if (await save.flush()) await backup.value?.flush() }
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
      <form class="b-form" novalidate @submit.prevent="saveAll">
      <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
        <fieldset :disabled="sidePending" v-for="section in orderedSections" :key="section.title" class="b-fieldset">
          <legend class="b-fieldset__legend">{{ section.title }}</legend>
          <template v-for="field in section.fields" :key="field.name"><div class="c-field" :class="{ 'is-invalid': save.fields.value[field.name]?.length }">
            <label v-if="field.kind !== 'checkbox'" class="c-field__label" :for="`setting-${field.name}`">{{ field.label }}<span v-if="field.required" class="c-field__req" aria-hidden="true">*</span></label>
            <label v-if="field.kind === 'checkbox'" class="c-check">
              <input :name="fieldName(field.name)" :required="field.required" :maxlength="field.maxlength" :id="`setting-${field.name}`" type="checkbox" :checked="Boolean(save.values.value[field.name])" @change="update(field.name, $event)" /><span>{{ field.label }}<span v-if="field.required" class="c-field__req" aria-hidden="true">*</span></span></label>
              <textarea v-else-if="field.kind === 'textarea'" :name="fieldName(field.name)" :required="field.required" :maxlength="field.maxlength" :id="`setting-${field.name}`" class="c-input" rows="3" :value="String(save.values.value[field.name])" @input="update(field.name, $event)" @blur="save.flush" />
              <select v-else-if="field.kind === 'select'" :name="fieldName(field.name)" :required="field.required" :id="`setting-${field.name}`" class="c-input" :value="save.values.value[field.name]" @change="update(field.name, $event)">
                <option v-for="choice in field.choices" :key="choice.value" :value="choice.value">{{ choice.label }}</option>
              </select>
              <input v-else :name="fieldName(field.name)" :required="field.required" :maxlength="field.maxlength" :id="`setting-${field.name}`" class="c-input" :type="field.kind" :value="save.values.value[field.name]" :min="field.min" :max="field.max" @input="update(field.name, $event)" @blur="save.flush" />
              <p v-if="field.help" class="c-field__help">{{ field.help }}</p>
              <p v-for="error in save.fields.value[field.name]" :key="error" class="c-field__error" role="alert">{{ error }}</p>
            </div>
<SettingsImages v-if="field.name === 'site_description'" only="site" :version="()=>save.snapshot.value.version" :settings="settings" :before-action="beforeSide" @changed="sideChanged" @settled="sideSettled" />
<SecretEditor v-if="field.name === 'smtp_username' || field.name === 'moderation_enabled'" embedded :field="field.name === 'smtp_username' ? 'smtp_password' : 'moderation_api_key'" :label="field.name === 'smtp_username' ? 'SMTP 密码' : '接口密钥'" :present="field.name === 'smtp_username' ? settings.has_smtp_password : settings.has_moderation_api_key" :before-action="beforeSide" @changed="sideChanged" @settled="sideSettled" />
</template>
<SettingsImages v-if="section.title === '栏目横幅'" only="banners" :version="()=>save.snapshot.value.version" :settings="settings" :before-action="beforeSide" @changed="sideChanged" @settled="sideSettled" />
          </fieldset>
          <BackupEditor ref="backup" embedded />

          <div class="b-formbar">
            <button hidden class="c-btn c-btn--primary" :disabled="save.pending.value">保存</button>
            <span class="b-formbar__note">改了就自动保存（密钥离开框时才存）；首页、横幅这些页面会跟着重新生成。</span>
          </div>
        </form>
      </div>
      <aside class="b-aside">
        <section class="b-section">
          <h2 class="b-section__title">检查</h2>
          <form class="b-form" @submit.prevent="testEmail"><button type="submit" class="c-btn c-btn--secondary c-btn--sm" :disabled="!email.canStart.value">发送测试邮件</button>
          <p class="b-sub">发给你自己的邮箱，用于检查 SMTP 配置。发送失败时会显示原因。</p>
          </form>
          <p v-if="emailMessage" class="b-sub" role="status">{{ emailMessage }}</p>
          <p class="b-sub">AI 巡查引擎按已批准的迁移安排在割接后启用。</p>
          <form class="b-form" @submit.prevent="backup?.test()"><button type="submit" class="c-btn c-btn--secondary c-btn--sm" :disabled="sidePending">测试对象存储</button>
          <p class="b-sub">用已保存的异地备份设置往存储桶里写一个小文件再删掉，看能不能连上、有没有权限。刚改的设置会先存好再测；「备份上传到对象存储」没打开也能测。</p>
          </form>
          <ActionState :message="email.message.value" :pending="email.pending.value" :uncertain="email.uncertain.value" @retry="email.retry" />
        </section>
      </aside>
    </div>
</template>
