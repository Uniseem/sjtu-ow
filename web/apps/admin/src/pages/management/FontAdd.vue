<script setup lang="ts">
import { ref } from "vue"
import { useRouter } from "vue-router"
import { importFont, type FontDetail } from "./pending"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import AdminPage from "../../components/AdminPage.vue"
import ActionState from "../../components/management/ActionState.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import { weightChoices } from "./font-format"
const api = useAdminApi()
const router = useRouter()
const family = ref("")
const displayName = ref("")
const weights = ref([400, 700])
const googleLicense = ref(false)
const packageLicense = ref(false)
const file = ref<File | null>(null)
import { useFontUpload } from "./use-font-upload"
const problem = ref("")
const uploadAction = useFontUpload(async result => { await router.push(`/admin/settings/fonts/${result.font.id}/`) })
type FontImport = Parameters<typeof importFont>[1]
const action = useAdminAction<FontImport, FontDetail>((body, extras) => importFont(api, body, extras), async result => { await router.push(`/admin/settings/fonts/${result.font.id}/`) })
function choose(event: Event) { file.value = (event.target as HTMLInputElement).files?.[0] ?? null; problem.value = '' }
async function upload() {
  if (!file.value || !uploadAction.canStart.value) return
  problem.value = ''
  await uploadAction.submit({ file: file.value, license: packageLicense.value })
}
</script>
<template>
  <AdminPage title="添加字体" section="设置" back-href="/admin/settings/fonts/">
    <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
    <p v-if="problem" class="c-field__error" role="alert">{{ problem }}</p>
    <ActionState :message="uploadAction.message.value" :pending="uploadAction.pending.value" :uncertain="uploadAction.uncertain.value" @retry="uploadAction.retry" />
    <p v-if="uploadAction.pending.value" class="b-sub" role="status">{{ uploadAction.stage.value }} {{ uploadAction.progress.value }}%</p>
    <section class="b-section">
      <h2 class="b-section__title">上传字体成品包</h2>
      <p class="b-section__text">选择已经处理好的字体成品包。服务器会核查清单、分片和授权。</p>
      <form class="b-form" @submit.prevent="upload">
        <label class="c-field__label" for="font-package">成品包</label>
        <input id="font-package" name="upload-file" type="file" accept=".zip" required class="c-input" :disabled="!uploadAction.canStart.value || !action.canStart.value" @change="choose" />
        <label class="c-check">
          <input v-model="packageLicense" name="upload-license_confirmed" required type="checkbox" />我确认字体授权允许在本站使用</label>
          <button class="c-btn c-btn--primary" :disabled="!file || !packageLicense || !uploadAction.canStart.value || !action.canStart.value">{{ uploadAction.pending.value ? '正在上传…' : '上传' }}</button>
        </form>
      </section>
      <section class="b-section">
        <h2 class="b-section__title">从 Google Fonts 下载</h2>
        <p class="b-section__text">服务器会把字体下载到本站保存，前台只使用本站副本。</p>
        <form class="b-form" novalidate @submit.prevent="action.submit({ source: 'google', family: family.trim(), display_name: displayName.trim(), weights, license_confirmed: googleLicense })">
          <div class="c-field"><label class="c-field__label" for="google-family">Google Fonts 字体名称<span class="c-field__req" aria-hidden="true">*</span></label>
          <input id="google-family" name="google-family_name" v-model="family" required class="c-input" maxlength="64" />
          <p class="c-field__help">填写 Google Fonts 上的名称，比如 Noto Serif SC。</p></div>
          <div class="c-field"><label class="c-field__label" for="google-name">站内显示名称</label>
          <input id="google-name" name="google-name" v-model="displayName" class="c-input" maxlength="64" />
          <p class="c-field__help">留空则使用上面的名称。</p></div>
          <fieldset class="c-field"><legend class="c-field__label mb-2">需要的字重<span class="c-field__req" aria-hidden="true">*</span></legend>
            <div><div v-for="choice in weightChoices" :key="choice.value"><label class="c-check"><input v-model="weights" name="google-weights" type="checkbox" :value="choice.value" /><span>{{ choice.label }}</span></label></div></div>
          </fieldset>
          <div class="c-field"><label class="c-check">
            <input v-model="googleLicense" name="google-license_confirmed" required type="checkbox" /><span>确认这个字体允许嵌入网站使用<span class="c-field__req" aria-hidden="true">*</span></span></label></div>
            <div class="b-actions"><button name="submit_google" type="submit" class="c-btn c-btn--primary" :disabled="!action.canStart.value || !uploadAction.canStart.value">下载</button></div>
          </form>
        </section>
        <div class="c-notice c-notice--info">
          <CIcon name="info" />
          <div class="c-notice__body">
            <strong>授权提醒：</strong>方正、汉仪等商业字体通常需要单独购买网页嵌入授权。字体文件里标记为禁止嵌入的，系统会直接拒绝处理。</div>
          </div>
        </AdminPage>
</template>
