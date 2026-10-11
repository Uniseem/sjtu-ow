<script setup lang="ts">
import { computed } from "vue"
import { useRoute } from "vue-router"
import { getApiLettersBatch } from "@sjtu-ow/api"
import { letterBatch,previewURL } from "@sjtu-ow/shared/letters"
import AdminPage from "../../components/AdminPage.vue"
import { useAdminApi } from "../../core/api"
import { useResource } from "../management/use-resource"
import ResourceState from "../../components/management/ResourceState.vue"
const route=useRoute()
const api=useAdminApi()
const resource=useResource(()=>route.fullPath,signal=>getApiLettersBatch(api,letterBatch(String(route.params.batch)),{signal,unauthorized:"throw"}))
const src=computed(()=>{
 const id=Number(route.params.id)
 const item=resource.data.value?.letters.find(letter=>letter.id===id)
 return item?previewURL(item.preview_url,String(route.params.batch),id):null
})
</script>
<template>
  <AdminPage title="信件预览" section="home" :back-href="'/admin/letters/' + encodeURIComponent(String(route.params.batch)) + '/'">
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <iframe v-if="src" class="c-mailframe" :src="src" title="信件预览" sandbox="" referrerpolicy="no-referrer" />
    <p v-else-if="resource.data.value" class="b-sub">这封信不存在或已经处理。</p>
  </AdminPage>
</template>
