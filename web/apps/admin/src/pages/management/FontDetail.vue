<script setup lang="ts">
import { ref,onUnmounted } from "vue"
import { useHead } from "@unhead/vue"
import { useRoute } from "vue-router"
import { deleteApiAdminFontsWeightsId,getApiAdminFontsWeightsIdDownload } from "@sjtu-ow/api"
import { getFont } from "./pending"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useResource } from "./use-resource"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import { bytes,source,status,weight } from "./font-format"
import { date } from "./format"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ActionState from "../../components/management/ActionState.vue"
import FontFaceUpload from "../../components/management/FontFaceUpload.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
const api=useAdminApi(),route=useRoute(),confirm=useConfirm()
const licenseLabels:Record<string,string>={open_source:'开源授权',web_license:'已购买网页嵌入授权',other:'其他'}
const resource=useResource(()=>route.params.id,signal=>getFont(api,String(route.params.id),{signal}))
useHead(()=>({link:resource.data.value?.faces_css_url?[{rel:'stylesheet',href:resource.data.value.faces_css_url}]:[]}))
const remove=useAdminAction<number,Awaited<ReturnType<typeof deleteApiAdminFontsWeightsId>>>((id,extras)=>deleteApiAdminFontsWeightsId(api,id,extras),result=>{resource.data.value=result})
const downloading=ref(false),downloadError=ref('')
let objectURL:string|undefined,flight:AbortController|undefined
async function download(id:number){if(downloading.value)return;downloading.value=true;downloadError.value='';flight=new AbortController();try{
 const result=await getApiAdminFontsWeightsIdDownload(api,id,{signal:flight.signal});const binary=atob(result.data_base64);const data=Uint8Array.from(binary,char=>char.charCodeAt(0));if(objectURL)URL.revokeObjectURL(objectURL);objectURL=URL.createObjectURL(new Blob([data],{type:'application/zip'}));const anchor=document.createElement('a');anchor.href=objectURL;anchor.download=result.filename.replace(/[\\/]/g,'_');anchor.click()
}catch(error){downloadError.value=error instanceof Error?error.message:'暂时无法下载。'}finally{downloading.value=false}}
function deleteWeight(id:number){if(remove.canStart.value&&confirm('删除这个字重？删除后不能恢复。'))void remove.submit(id)}
onUnmounted(()=>{flight?.abort();if(objectURL)URL.revokeObjectURL(objectURL)})
</script>
<template>
 <AdminPage :title="resource.data.value?.font.display_name||'字体'" section="设置" back-href="/admin/settings/fonts/">
  <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
  <div v-if="resource.data.value" class="b-split"><div class="b-form">
   <table class="c-table c-table--stack"><thead><tr><th>字重</th><th>状态</th><th class="is-num">分片</th><th class="is-num">总大小</th><th class="is-num">字符数</th><th>预览</th><th><span class="sr-only">操作</span></th></tr></thead><tbody><tr v-for="face in resource.data.value.slices" :key="face.id"><td>{{ weight(face.weight,face.style) }}</td><td data-label="状态">{{ status(face.status) }}<span v-if="face.error" class="b-sub split-problem">{{ face.error }}</span></td><td class="is-num" data-label="分片">{{ face.files }}</td><td class="is-num" data-label="总大小">{{ bytes(face.bytes) }}</td><td class="is-num" data-label="字符数">{{ face.glyph_count }}</td><td data-label="预览"><span v-if="face.status==='ready'" :class="`font-preview-${resource.data.value.font.id}-${face.weight}-${face.style}`">SJTU-OW 上海交通大学守望先锋 2026 钻石 3 · Genji#51234</span><template v-else>—</template></td><td><div class="b-rowacts"><a class="c-btn c-btn--quiet c-btn--sm" :href="`/admin/settings/fonts/weights/${face.id}/download/`" :aria-disabled="downloading" @click.prevent="download(face.id)">下载</a><form @submit.prevent="deleteWeight(face.id)"><button type="submit" class="c-btn c-btn--quiet c-btn--sm" :disabled="!face.can_delete || !remove.canStart.value">删除字重</button></form></div></td></tr><tr v-if="!resource.data.value.slices.length"><td colspan="7">还没有字重。</td></tr></tbody></table>
   <p v-if="downloadError" class="c-field__error" role="alert">{{ downloadError }}</p><ActionState :message="remove.message.value" :pending="remove.pending.value" :uncertain="remove.uncertain.value" @retry="remove.retry" />
   <FontFaceUpload :id="resource.data.value.font.id" @changed="resource.data.value=$event" />
  </div><aside class="b-aside"><section class="b-section"><dl class="b-kv"><dt>样式表字体名</dt><dd class="b-mono">{{ resource.data.value.font.css_name }}</dd><dt>来源</dt><dd>{{ source(resource.data.value.font.source) }}<template v-if="resource.data.value.font.source_ref">（{{ resource.data.value.font.source_ref }}）</template></dd><dt>授权</dt><dd>{{ licenseLabels[resource.data.value.font.license_type] || resource.data.value.font.license_type || resource.data.value.font.license }}<template v-if="resource.data.value.font.license_note">：{{ resource.data.value.font.license_note }}</template></dd><dt>磁盘占用</dt><dd>{{ bytes(resource.data.value.font.bytes) }}（字体分片）</dd><dt>添加人</dt><dd>{{ resource.data.value.font.created_by_name || '—' }}，{{ date(resource.data.value.font.created_at) }}</dd></dl><div v-if="resource.data.value.font.used_by.length" class="c-notice c-notice--info"><CIcon name="info" /><div class="c-notice__body">正在被排版区域使用：{{ resource.data.value.font.used_by.join('、') }}。删除前需要先在排版设置里换掉。</div></div><div class="b-actions"><RouterLink class="c-btn c-btn--danger c-btn--sm" :to="`/admin/settings/fonts/${resource.data.value.font.id}/delete/`">删除字体</RouterLink></div></section></aside></div>
 </AdminPage>
</template>
