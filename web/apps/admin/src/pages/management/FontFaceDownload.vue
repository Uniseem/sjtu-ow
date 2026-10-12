<script setup lang="ts">
import {ref,onMounted,onUnmounted} from 'vue'
import {useRoute} from 'vue-router'
import {getApiAdminFontsWeightsIdDownload} from '@sjtu-ow/api'
import {useAdminApi} from '../../core/api'
import {showReadError} from '../../core/read-error'
import AdminPage from '../../components/AdminPage.vue'
const api=useAdminApi(),route=useRoute(),pending=ref(false),message=ref(''),error=ref('')
let objectURL:string|undefined
const controller=new AbortController()
async function download(){if(pending.value)return;pending.value=true;error.value='';try{const result=await getApiAdminFontsWeightsIdDownload(api,String(route.params.id),{signal:controller.signal});const binary=atob(result.data_base64);const data=Uint8Array.from(binary,char=>char.charCodeAt(0));if(objectURL)URL.revokeObjectURL(objectURL);objectURL=URL.createObjectURL(new Blob([data],{type:'application/zip'}));const link=document.createElement('a');link.href=objectURL;link.download=result.filename.replace(/[\\/]/g,'_');link.click();message.value='字体成品包已准备好。'}catch(failure){showReadError(failure);error.value=failure instanceof Error?failure.message:'暂时无法下载。'}finally{pending.value=false}}
onMounted(()=>{void download()});onUnmounted(()=>{controller.abort();if(objectURL)URL.revokeObjectURL(objectURL)})
</script>
<template><AdminPage title="下载字体字重" section="设置" back-href="/admin/settings/fonts/"><p v-if="pending" class="b-section__text" role="status" aria-busy="true">正在准备字体成品包…</p><p v-if="message" class="b-section__text">{{message}}</p><p v-if="error" class="c-field__error" role="alert">{{error}}</p><button type="button" class="c-btn c-btn--secondary" :disabled="pending" @click="download">下载</button></AdminPage></template>
