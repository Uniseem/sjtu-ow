<script setup lang="ts">
import {useRoute,useRouter} from 'vue-router'
import {getFont,deleteFont} from './pending'
import {useResource} from './use-resource'
import {useAdminApi} from '../../core/api'
import {useAdminAction} from '../../core/use-action'
import AdminPage from '../../components/AdminPage.vue'
import ResourceState from '../../components/management/ResourceState.vue'
import ActionState from '../../components/management/ActionState.vue'
import CIcon from '@sjtu-ow/ui/CIcon.vue'
const api=useAdminApi(),route=useRoute(),router=useRouter()
const resource=useResource(()=>route.params.id,signal=>getFont(api,String(route.params.id),{signal}))
const remove=useAdminAction<null,{result:string}>((_,extras)=>deleteFont(api,String(route.params.id),extras),async()=>{await router.push('/admin/settings/fonts/')})
function submit(){if(remove.canStart.value)void remove.submit(null)}
</script>
<template>
 <AdminPage :title="resource.data.value?.font ? `删除「${resource.data.value.font.display_name||resource.data.value.font.family}」`:'删除字体'" section="设置" :back-href="`/admin/settings/fonts/${route.params.id}/`">
  <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
  <section v-if="resource.data.value" class="b-section"><template v-if="!resource.data.value.font.can_delete"><div class="c-notice c-notice--error"><CIcon name="x-circle" /><div class="c-notice__body">「{{resource.data.value.font.display_name||resource.data.value.font.family}}」正在被排版区域使用（{{resource.data.value.font.used_by.join('、')}}），不能删除。请先在排版设置里把这些区域换成其他字体。</div></div><div class="b-actions"><RouterLink class="c-btn c-btn--secondary" to="/admin/settings/typography/">前往排版设置</RouterLink></div></template><template v-else><p class="b-section__text">确定删除字体「{{resource.data.value.font.display_name||resource.data.value.font.family}}」吗？字体库记录会被移除，未被其他字体或正在上传的文件引用的切片会安全回收；共享切片保留。此操作无法恢复。</p><form class="b-actions" @submit.prevent="submit"><button type="submit" class="c-btn c-btn--danger" :disabled="!remove.canStart.value">确认删除</button><RouterLink class="c-btn c-btn--secondary" :to="`/admin/settings/fonts/${route.params.id}/`">取消</RouterLink></form></template><ActionState :message="remove.message.value" :pending="remove.pending.value" :uncertain="remove.uncertain.value" @retry="remove.retry" /></section>
 </AdminPage>
</template>
