<script setup lang="ts">
import { ref } from "vue"
import { patchApiAdminSettingsBackup, postApiAdminSettingsBackupSecret, type CallExtras } from "@sjtu-ow/api"
import type { SaveRequest } from "@sjtu-ow/shared/autosave"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useAdminSave } from "../../core/use-save"
import type { BackupPage, BackupValues } from "../../pages/management/pending"
import SaveStatus from "../SaveStatus.vue"
import ActionState from "./ActionState.vue"
const props = defineProps<{ data: BackupPage }>()
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
const fields: { key: keyof Values; label: string; type: string }[] = [
  { key: 'endpoint', label: '对象存储地址', type: 'url' }, { key: 'region', label: '区域', type: 'text' }, { key: 'bucket', label: '存储桶', type: 'text' }, { key: 'prefix', label: '路径前缀', type: 'text' }, { key: 'access_key_id', label: 'Access Key ID', type: 'text' }, { key: 'retention_days', label: '保留天数', type: 'number' },
]
function update(key: keyof Values, event: Event) { const input = event.target as HTMLInputElement; save.set(key, (typeof save.values.value[key] === 'number' ? Number(input.value) : input.value) as never, typeof save.values.value[key] === 'number' ? 'choice' : 'text') }
async function saveSecret() { if (secret.value && await save.flush()) await action.submit(secret.value) }
defineExpose({test})
async function test() { if (!(await save.flush())) return; if (secret.value && !(await action.submit(secret.value))) return; emit('test') }
</script>
<template>
  <form class="b-form" @submit.prevent="save.save">
    <label class="c-check">
      <input type="checkbox" :checked="save.values.value.enabled" @change="save.set('enabled', ($event.target as HTMLInputElement).checked, 'choice')" />备份上传到对象存储</label>
      <div v-for="field in fields" :key="field.key" class="c-field" :class="{ 'is-invalid': save.fields.value[field.key]?.length }">
        <label class="c-field__label" :for="`backup-${field.key}`">{{ field.label }}</label>
        <input :id="`backup-${field.key}`" class="c-input" :type="field.type" :value="save.values.value[field.key]" @input="update(field.key, $event)" @blur="save.flush" />
        <p v-for="error in save.fields.value[field.key]" :key="error" class="c-field__error" role="alert">{{ error }}</p>
      </div>
      <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
      <button class="c-btn c-btn--primary" :disabled="save.pending.value">保存</button>
    </form>
    <form class="b-form" @submit.prevent="saveSecret">
      <label class="c-field__label" for="backup-secret">Secret Access Key</label>
      <input id="backup-secret" v-model="secret" type="password" autocomplete="new-password" class="c-input" />
      <p class="b-sub">{{ hasSecret ? '现在有已保存的密钥。' : '现在没有保存密钥。' }} 密钥不回显，空着不改。</p>
      <button class="c-btn c-btn--secondary c-btn--sm" :disabled="!secret || !action.canStart.value">保存密钥</button>
      <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
    </form>
    <button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="save.pending.value || !action.canStart.value" @click="test">测试对象存储</button>
</template>
