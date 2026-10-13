<script setup lang="ts">
import { ref } from "vue"
import { onBeforeRouteLeave, onBeforeRouteUpdate } from "vue-router"
import { patchApiAdminSettingsBackup, postApiAdminSettingsBackupSecret, type CallExtras } from "@sjtu-ow/api"
import type { SaveRequest } from "@sjtu-ow/shared/autosave"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useAdminSave } from "../../core/use-save"
import type { BackupPage, BackupValues } from "../../pages/management/pending"
import SaveStatus from "../SaveStatus.vue"
import ActionState from "./ActionState.vue"
const props = defineProps<{ data: BackupPage; embedded?: boolean }>()
const emit = defineEmits<{ test: []; changed: [] }>()
const api = useAdminApi()
type Values = Omit<BackupValues, 'has_secret_access_key'>
const v = props.data.values
const secret = ref("")
const hasSecret = ref(v.has_secret_access_key)
import { formReceipt } from "../../pages/management/save-projection"
async function patch(body: SaveRequest<Values>, extras: CallExtras) { return formReceipt(await patchApiAdminSettingsBackup(api, body, extras), initial) }
import { currentReader } from "../../pages/management/current-reader"
const initial: Values = { enabled: v.enabled, endpoint: v.endpoint, region: v.region, bucket: v.bucket, prefix: v.prefix, access_key_id: v.access_key_id, retention_days: v.retention_days }
const save = useAdminSave<Values>({ initial, version: props.data.version, readCurrent: currentReader(initial), transport: (body, key, signal) => patch(body, { key, signal }) })
const action = useAdminAction<string, { has_secret_access_key: boolean }>((value, extras) => postApiAdminSettingsBackupSecret(api, { secret_access_key: value,clear:false }, extras), response => { secret.value = ''; hasSecret.value = response.has_secret_access_key; emit('changed') })
const fields: { key: keyof Values; label: string; type: string; help?: string; maxlength?: number }[] = [
  { key: 'endpoint', label: '对象存储地址', type: 'url', help: 'Cloudflare R2 形如 https://<账号ID>.r2.cloudflarestorage.com', maxlength: 200 },
  { key: 'bucket', label: '存储桶', type: 'text', maxlength: 64 },
  { key: 'region', label: '区域', type: 'text', help: 'R2 填 auto。', maxlength: 32 },
  { key: 'access_key_id', label: '访问密钥 ID（Access Key ID）', type: 'text', maxlength: 128 },
  { key: 'prefix', label: '路径前缀', type: 'text', help: '存到桶里的哪个目录下。', maxlength: 128 },
  { key: 'retention_days', label: '备份保留天数', type: 'number', help: '本地与对象存储备份均按此天数清理；关闭上传仍会清理本地备份。' },
]
function fieldName(key: keyof Values) { return key === 'enabled' ? 'backup_s3_enabled' : key === 'retention_days' ? 'backup_retention_days' : `backup_s3_${key}` }
function update(key: keyof Values, event: Event) { const input = event.target as HTMLInputElement; save.set(key, (typeof save.values.value[key] === 'number' ? Number(input.value) : input.value) as never, typeof save.values.value[key] === 'number' ? 'choice' : 'text') }
async function saveSecret() { if (action.canStart.value && secret.value && await save.flush()) await action.submit(secret.value) }
async function leaveSecret() { if (secret.value && action.canStart.value) await saveSecret(); return !secret.value && !action.pending.value && !action.uncertain.value }
onBeforeRouteLeave(leaveSecret)
onBeforeRouteUpdate(leaveSecret)
defineExpose({test, flush: async () => { if (!(await save.flush())) return false; return !secret.value || await action.submit(secret.value) }})
async function test() { if (!(await save.flush())) return; if (secret.value && !(await action.submit(secret.value))) return; emit('test') }
</script>
<template>
  <component :is="embedded ? 'div' : 'form'" :class="embedded ? 'contents' : 'b-form'" @submit.prevent="save.save">
      <SaveStatus v-if="!embedded || save.dirty.value || save.pending.value || save.snapshot.value.state === 'failed' || save.snapshot.value.state === 'partial'" :idle-message="embedded ? '' : undefined" :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
    <div class="c-field"><label class="c-check">
      <input name="backup_s3_enabled" type="checkbox" :checked="save.values.value.enabled" @change="save.set('enabled', ($event.target as HTMLInputElement).checked, 'choice')" /><span>备份上传到对象存储</span></label><p class="c-field__help">开启后，每次备份完会加密并上传一份。需要先设好下面几项。</p></div>
      <template v-for="field in fields" :key="field.key"><div class="c-field" :class="{ 'is-invalid': save.fields.value[field.key]?.length }">
        <label class="c-field__label" :for="`backup-${field.key}`">{{ field.label }}</label>
        <input :id="`backup-${field.key}`" :name="fieldName(field.key)" class="c-input" :type="field.type" :maxlength="field.maxlength" :min="field.key === 'retention_days' ? 1 : undefined" :max="field.key === 'retention_days' ? 365 : undefined" :value="save.values.value[field.key]" @input="update(field.key, $event)" @blur="save.flush" />
        <p v-if="field.help" class="c-field__help">{{ field.help }}</p>
        <p v-for="error in save.fields.value[field.key]" :key="error" class="c-field__error" role="alert">{{ error }}</p>
      </div>
    <div v-if="field.key === 'access_key_id'" class="c-field">
      <label class="c-field__label" for="backup-secret">密钥（Secret Access Key）</label>
      <input id="backup-secret" name="backup_s3_secret_access_key" v-model="secret" type="password" autocomplete="new-password" class="c-input" :placeholder="!embedded && hasSecret ? '已保存（留空不修改）' : undefined" @blur="saveSecret" />
      <p class="c-field__help">加密存储。留空表示不修改已保存的密钥。{{ hasSecret ? '现在：已保存。' : '现在：还没有。' }}</p>
      <button v-if="!embedded" type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="!secret || !action.canStart.value" @click="saveSecret">保存密钥</button>
      <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
    </div></template>
      <button hidden v-if="!embedded" class="c-btn c-btn--primary" :disabled="save.pending.value">保存</button>
    </component>
    <button v-if="!embedded" type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="save.pending.value || !action.canStart.value" @click="test">测试对象存储</button>
</template>
