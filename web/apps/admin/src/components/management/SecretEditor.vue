<script setup lang="ts">
import { ref,watch } from "vue"
import { onBeforeRouteLeave, onBeforeRouteUpdate } from "vue-router"
import { ApiError, patchApiAdminSettings } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import ActionState from "./ActionState.vue"
import ConfirmAction from "./ConfirmAction.vue"
const props = defineProps<{ field: 'smtp_password' | 'moderation_api_key'; label: string; present: boolean; embedded?: boolean; beforeAction: () => Promise<boolean> }>()
const emit=defineEmits<{changed:[settings:NonNullable<Awaited<ReturnType<typeof patchApiAdminSettings>>["settings"]>];settled:[]}>()
const api = useAdminApi()
const value = ref("")
const hasSecret = ref(props.present)
const savedMessage = ref("")
const action = useAdminAction<{ value: string; clear: boolean }, Awaited<ReturnType<typeof patchApiAdminSettings>>>((body, extras) => {
  const changes = props.field === 'smtp_password' ? body.clear ? { clear_smtp_password: true } : { smtp_password: body.value } : body.clear ? { clear_moderation_api_key: true } : { moderation_api_key: body.value }
  return patchApiAdminSettings(api, changes, extras)
}, result => {
  if (!result.settings) throw new ApiError(0,"invalid_receipt","密钥保存回执无效，请重试。")
  hasSecret.value = props.field === 'smtp_password' ? result.settings.has_smtp_password : result.settings.has_moderation_api_key
  emit("changed",result.settings)
  value.value = ""
  savedMessage.value = '已保存。'
})
async function submit(clear: boolean) { if (!action.canStart.value) return; if (!clear && !value.value) return; if (await props.beforeAction()) await action.submit({ value: clear ? '' : value.value, clear }) }
async function leave() { if (value.value && action.canStart.value) await submit(false); return !value.value && !action.pending.value && !action.uncertain.value }
onBeforeRouteLeave(leave)
onBeforeRouteUpdate(leave)
watch(()=>[action.pending.value,action.uncertain.value],([pending,uncertain])=>{if(!pending&&!uncertain)emit("settled")})
</script>
<template>
  <div :class="embedded ? 'c-field' : 'b-section'">
    <h2 v-if="!embedded" class="b-section__title">{{ label }}</h2>
    <p v-if="!embedded" class="b-sub">{{ hasSecret ? '现在有已保存的密钥。' : '现在没有保存密钥。' }} 密钥不回显，空着不改。</p>
    <component :is="embedded ? 'div' : 'form'" :class="embedded ? 'contents' : undefined" @submit.prevent="submit(false)">
      <label class="c-field__label" :for="`secret-${field}`">{{ embedded ? label : `新的${label}` }}</label>
      <input :id="`secret-${field}`" v-model="value" type="password" autocomplete="new-password" class="c-input" :name="field" :placeholder="!embedded && hasSecret ? '已保存（留空不修改）' : undefined" :disabled="!action.canStart.value" @blur="submit(false)" />
      <p v-if="embedded" class="c-field__help">{{ field === 'smtp_password' ? '加密存储。留空表示不修改已保存的密码。' : '服务商给的 API Key，加密存储。留空表示不修改已保存的密钥。' }}{{ hasSecret ? '现在：已保存。' : '现在：还没有。' }}</p><div v-if="!embedded" class="b-actions">
        <button class="c-btn c-btn--secondary c-btn--sm" :disabled="!value || !action.canStart.value">保存{{ label }}</button>
        <ConfirmAction v-if="hasSecret" title="清除密钥" :message="`清除已保存的${label}？`" label="清除" danger :pending="!action.canStart.value" @confirm="submit(true)" />
      </div>
    </component>
    <p v-if="savedMessage" class="b-sub" role="status">{{ savedMessage }}</p>
    <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
  </div>
</template>
