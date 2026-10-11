<script setup lang="ts">
import { ref,watch } from "vue"
import { patchApiAdminSettings } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import ActionState from "./ActionState.vue"
import ConfirmAction from "./ConfirmAction.vue"
const props = defineProps<{ field: 'smtp_password' | 'moderation_api_key'; label: string; present: boolean; beforeAction: () => Promise<boolean> }>()
const emit=defineEmits<{changed:[settings:NonNullable<Awaited<ReturnType<typeof patchApiAdminSettings>>["settings"]>];settled:[]}>()
const api = useAdminApi()
const value = ref("")
const hasSecret = ref(props.present)
const savedMessage = ref("")
const action = useAdminAction<{ value: string; clear: boolean }, Awaited<ReturnType<typeof patchApiAdminSettings>>>((body, extras) => {
  const changes = props.field === 'smtp_password' ? body.clear ? { clear_smtp_password: true } : { smtp_password: body.value } : body.clear ? { clear_moderation_api_key: true } : { moderation_api_key: body.value }
  return patchApiAdminSettings(api, changes, extras)
}, result => {
  if (!result.settings) return
  hasSecret.value = props.field === 'smtp_password' ? result.settings.has_smtp_password : result.settings.has_moderation_api_key
  emit("changed",result.settings)
  value.value = ""
  savedMessage.value = '已保存。'
})
async function submit(clear: boolean) { if (!clear && !value.value) return; if (await props.beforeAction()) await action.submit({ value: clear ? '' : value.value, clear }) }
watch(()=>[action.pending.value,action.uncertain.value],([pending,uncertain])=>{if(!pending&&!uncertain)emit("settled")})
</script>
<template>
  <section class="b-section">
    <h2 class="b-section__title">{{ label }}</h2>
    <p class="b-sub">{{ hasSecret ? '现在有已保存的密钥。' : '现在没有保存密钥。' }} 密钥不回显，空着不改。</p>
    <form @submit.prevent="submit(false)">
      <label class="c-field__label" :for="`secret-${field}`">新的{{ label }}</label>
      <input :id="`secret-${field}`" v-model="value" type="password" autocomplete="new-password" class="c-input" :disabled="!action.canStart.value" />
      <div class="b-actions">
        <button class="c-btn c-btn--secondary c-btn--sm" :disabled="!value || !action.canStart.value">保存{{ label }}</button>
        <ConfirmAction v-if="hasSecret" title="清除密钥" :message="`清除已保存的${label}？`" label="清除" danger :pending="!action.canStart.value" @confirm="submit(true)" />
      </div>
    </form>
    <p v-if="savedMessage" class="b-sub" role="status">{{ savedMessage }}</p>
    <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
  </section>
</template>
