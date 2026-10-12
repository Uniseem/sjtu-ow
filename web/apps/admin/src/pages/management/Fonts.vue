<script setup lang="ts">
import { useHead } from "@unhead/vue"
import { getFonts } from "./pending"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import { bytes,source,status,license } from "./font-format"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
const api=useAdminApi()
const resource=useResource(()=>true,signal=>getFonts(api,{signal}))
useHead(()=>({link:resource.data.value?.faces_css_url?[{rel:'stylesheet',href:resource.data.value.faces_css_url}]:[]}))
</script>
<template>
 <AdminPage title="字体库" section="设置">
  <template #actions><RouterLink to="/admin/settings/fonts/add/" class="c-btn c-btn--primary c-btn--sm"><CIcon name="plus" />添加字体</RouterLink></template>
  <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
  <table v-if="resource.data.value?.fonts.length" class="c-table c-table--stack"><thead><tr><th>名称</th><th>样式表字体名</th><th>来源</th><th>授权</th><th>字重</th><th>磁盘占用</th><th>预览</th></tr></thead><tbody><tr v-for="font in resource.data.value.fonts" :key="font.id"><td><RouterLink class="b-title" :to="`/admin/settings/fonts/${font.id}/`">{{ font.display_name||font.family }}</RouterLink></td><td data-label="样式表字体名"><span class="b-mono">{{ font.css_name }}</span></td><td data-label="来源">{{ source(font.source) }}</td><td data-label="授权">{{ license(font.license_type || font.license) }}</td><td data-label="字重"><template v-for="(value,index) in font.weights" :key="value">{{ value }}（{{ status(font.status) }}）{{ index<font.weights.length-1?'、':'' }}</template><template v-if="!font.weights.length">尚未添加字重</template></td><td data-label="磁盘占用">{{ bytes(font.bytes) }}</td><td data-label="预览" :class="`font-preview-${font.id}`">SJTU-OW 上海交通大学守望先锋 2026 钻石 3 · Genji#51234</td></tr></tbody></table>
  <CEmpty v-else-if="!resource.pending.value && !resource.message.value" title="字体库还是空的" message="全站正在使用系统字体。" action-url="/admin/settings/fonts/add/" action-label="添加字体" />
 </AdminPage>
</template>
