<script setup lang="ts">
import { ref } from "vue"
import { useRouter } from "vue-router"
import { importFont, type FontDetail } from "./pending"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import AdminPage from "../../components/AdminPage.vue"
import ActionState from "../../components/management/ActionState.vue"
const api = useAdminApi()
const router = useRouter()
const family = ref("")
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
        <input id="font-package" type="file" accept=".zip" class="c-input" :disabled="!uploadAction.canStart.value || !action.canStart.value" @change="choose" />
        <label class="c-check">
          <input v-model="packageLicense" type="checkbox" />我确认字体授权允许在本站使用</label>
          <button class="c-btn c-btn--primary" :disabled="!file || !packageLicense || !uploadAction.canStart.value || !action.canStart.value">{{ uploadAction.pending.value ? '正在上传…' : '上传' }}</button>
        </form>
      </section>
      <section class="b-section">
        <h2 class="b-section__title">从 Google Fonts 下载</h2>
        <p class="b-section__text">服务器会把字体下载到本站保存，前台只使用本站副本。</p>
        <form class="b-form" @submit.prevent="action.submit({ source: 'google', family: family.trim(), license_confirmed: googleLicense })">
          <label class="c-field__label" for="google-family">字体家族名称</label>
          <input id="google-family" v-model="family" class="c-input" placeholder="Noto Sans SC" maxlength="120" />
          <label class="c-check">
            <input v-model="googleLicense" type="checkbox" />我确认字体授权允许在本站使用</label>
            <button class="c-btn c-btn--primary" :disabled="!family.trim() || !googleLicense || !action.canStart.value || !uploadAction.canStart.value">下载</button>
          </form>
        </section>
        <div class="c-notice c-notice--info">
          <div class="c-notice__body">
            <strong>授权提醒：</strong>方正、汉仪等商业字体通常需要单独购买网页嵌入授权。字体文件里标记为禁止嵌入的，系统会直接拒绝处理。</div>
          </div>
        </AdminPage>
</template>
