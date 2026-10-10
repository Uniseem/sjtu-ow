<script setup lang="ts">
import { ref, onMounted } from "vue"
import {
  getApiAdminSettings,
  patchApiAdminSettings,
  postApiAdminSettingsTestEmail,
  type GetApiAdminSettingsOut,
} from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"
import { useApi } from "../../api"

const api = useApi()

const settingsSection = ADMIN_SECTIONS.find((s) => s.id === "settings")
const loading = ref(true)
const saving = ref(false)
const testingEmail = ref(false)
const settings = ref<GetApiAdminSettingsOut["settings"] | null>(null)
const successMsg = ref<string | null>(null)
const error = ref<string | null>(null)

// Form state
const siteDescription = ref("")
const foundedOn = ref("")
const smtpHost = ref("")
const smtpPort = ref<number | undefined>(undefined)
const smtpUsername = ref("")
const smtpPassword = ref("")
const smtpSender = ref("")
const smtpUseTls = ref(true)

// AI settings
const aiEnabled = ref(false)
const aiEndpoint = ref("")
const aiApiKey = ref("")
const aiModel = ref("")

async function loadSettings() {
  loading.value = true
  try {
    const res = await getApiAdminSettings(api)
    settings.value = res.settings
    if (res.settings) {
      siteDescription.value = res.settings.site_description ?? ""
      foundedOn.value = res.settings.founded_on ?? ""
      smtpHost.value = res.settings.smtp_host ?? ""
      smtpPort.value = res.settings.smtp_port
      smtpUsername.value = res.settings.smtp_username ?? ""
      smtpSender.value = res.settings.smtp_sender ?? ""
      smtpUseTls.value = res.settings.smtp_use_tls
      aiEnabled.value = res.settings.ai_moderation_enabled
      aiEndpoint.value = res.settings.ai_api_endpoint ?? ""
      aiModel.value = res.settings.ai_model ?? ""
    }
  } catch (err: any) {
    error.value = err?.message ?? "加载全站设置失败"
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  successMsg.value = null
  error.value = null
  try {
    await patchApiAdminSettings(api, {
      site_description: siteDescription.value,
      founded_on: foundedOn.value,
      smtp_host: smtpHost.value,
      smtp_port: smtpPort.value ? Number(smtpPort.value) : undefined,
      smtp_username: smtpUsername.value,
      smtp_password: smtpPassword.value ? smtpPassword.value : undefined,
      smtp_sender: smtpSender.value,
      smtp_use_tls: smtpUseTls.value,
      ai_moderation_enabled: aiEnabled.value,
      ai_api_endpoint: aiEndpoint.value,
      ai_api_key: aiApiKey.value ? aiApiKey.value : undefined,
      ai_model: aiModel.value,
    })
    successMsg.value = "全站设置已成功保存"
    smtpPassword.value = ""
    aiApiKey.value = ""
    await loadSettings()
  } catch (err: any) {
    error.value = err?.message ?? "保存设置失败"
  } finally {
    saving.value = false
  }
}

async function testEmail() {
  testingEmail.value = true
  successMsg.value = null
  error.value = null
  try {
    const res = await postApiAdminSettingsTestEmail(api)
    successMsg.value = res.message ?? "测试邮件发送成功，请查收邮箱！"
  } catch (err: any) {
    error.value = err?.message ?? "发送测试邮件失败，请检查 SMTP 配置"
  } finally {
    testingEmail.value = false
  }
}

onMounted(() => {
  loadSettings()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="设置"
      title="全站设置"
      :tabs="settingsSection?.tabs"
      active-tab="site"
    >
      <template #actions>
        <button class="c-btn c-btn--primary c-btn--sm" :disabled="saving" @click="saveSettings">
          <CIcon name="check" class="size-4 mr-1" />
          {{ saving ? '正在保存...' : '保存全站设置' }}
        </button>
      </template>
    </AdminHead>

    <div class="b-main">
      <div v-if="successMsg" class="c-notice c-notice--success mb-4">
        <p>{{ successMsg }}</p>
      </div>
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <div class="space-y-6 max-w-4xl">
        <!-- 站点基本信息 -->
        <section class="b-section p-6 rounded-lg bg-surface border border-border shadow-xs">
          <h2 class="text-base font-bold text-fg mb-4 pb-2 border-b border-border">站点基本信息</h2>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-semibold mb-1">社区成立日期</label>
              <input v-model="foundedOn" type="text" class="c-input w-full" placeholder="例如：2016-10-15" />
            </div>
            <div>
              <label class="block text-sm font-semibold mb-1">站点名称</label>
              <input type="text" value="SJTU-OW" disabled class="c-input w-full bg-surface-2 opacity-80" />
            </div>
            <div class="md:col-span-2">
              <label class="block text-sm font-semibold mb-1">站点简介与页脚说明</label>
              <textarea v-model="siteDescription" rows="2" class="c-input w-full resize-y" />
            </div>
          </div>
        </section>

        <!-- SMTP 邮件设置 -->
        <section class="b-section p-6 rounded-lg bg-surface border border-border shadow-xs">
          <div class="flex justify-between items-center mb-4 pb-2 border-b border-border">
            <h2 class="text-base font-bold text-fg">SMTP 邮件发信服务配置</h2>
            <button
              class="c-btn c-btn--secondary c-btn--xs"
              :disabled="testingEmail"
              @click="testEmail"
            >
              <CIcon name="mail" class="size-3.5 mr-1" />
              {{ testingEmail ? '正在发信...' : '发送测试邮件至当前邮箱' }}
            </button>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <label class="block text-sm font-semibold mb-1">SMTP 服务器主机</label>
              <input v-model="smtpHost" type="text" class="c-input w-full" placeholder="smtp.example.com" />
            </div>
            <div>
              <label class="block text-sm font-semibold mb-1">端口</label>
              <input v-model="smtpPort" type="number" class="c-input w-full" placeholder="465 / 587" />
            </div>
            <div>
              <label class="block text-sm font-semibold mb-1">发信账号 / 用户名</label>
              <input v-model="smtpUsername" type="text" class="c-input w-full" />
            </div>
            <div>
              <label class="block text-sm font-semibold mb-1">发信密码 / 授权码</label>
              <input
                v-model="smtpPassword"
                type="password"
                class="c-input w-full"
                :placeholder="settings?.has_smtp_password ? '已设置（留空表示不修改）' : '未设置'"
              />
            </div>
            <div class="md:col-span-2">
              <label class="block text-sm font-semibold mb-1">发件人地址 (Sender)</label>
              <input v-model="smtpSender" type="text" class="c-input w-full" placeholder="no-reply@example.com" />
            </div>
          </div>
        </section>

        <!-- AI 巡查配置 -->
        <section class="b-section p-6 rounded-lg bg-surface border border-border shadow-xs">
          <h2 class="text-base font-bold text-fg mb-4 pb-2 border-b border-border">AI 内容审核服务配置</h2>
          <div class="space-y-4">
            <div class="flex items-center gap-2">
              <input id="ai-toggle" v-model="aiEnabled" type="checkbox" class="c-checkbox" />
              <label for="ai-toggle" class="text-sm font-semibold cursor-pointer">开启 AI 内容自动巡查与初审</label>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <label class="block text-sm font-semibold mb-1">API 端点地址</label>
                <input v-model="aiEndpoint" type="text" class="c-input w-full" placeholder="https://api.deepseek.com/v1" />
              </div>
              <div>
                <label class="block text-sm font-semibold mb-1">模型名称</label>
                <input v-model="aiModel" type="text" class="c-input w-full" placeholder="deepseek-chat" />
              </div>
              <div class="md:col-span-2">
                <label class="block text-sm font-semibold mb-1">API 密钥 (Key)</label>
                <input
                  v-model="aiApiKey"
                  type="password"
                  class="c-input w-full"
                  :placeholder="settings?.has_ai_api_key ? '已配置安全密钥（留空不修改）' : '输入 API Key'"
                />
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
