<script setup lang="ts">
import { computed, onMounted, watch } from "vue"
import { useRoute } from "vue-router"
import { ApiError } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import { useContentResource } from "../content/use-resource"
import { getMailSample } from "./pending"
import MailSampleCard from "./MailSampleCard.vue"
const api = useAdminApi()
const route = useRoute()
const key = computed(() => typeof route.params.key === "string" ? route.params.key : "")
const resource = useContentResource(async (signal) => {
  if (!/^[a-z][a-z0-9-]{0,63}$/.test(key.value)) throw new ApiError(404, "not_found", "邮件样张不存在。")
  return getMailSample(api, key.value, { signal })
})
onMounted(() => { void resource.load() })
watch(() => key.value, () => { void resource.load() })
</script>
<template>
  <AdminPage :title="resource.data.value?.title || '邮件样张'" section="settings" back-href="/admin/settings/email-samples/">
    <ContentLoad :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.load" />
    <template v-if="resource.data.value && !resource.pending.value">
      <p class="c-notice c-notice--info">这是固定虚构数据的样张。HTML 和纯文本都使用实际发信的信纸渲染；打开这页不会发送邮件。</p>
      <MailSampleCard :key="resource.data.value.key" :sample="resource.data.value" detail />
    </template>
  </AdminPage>
</template>
