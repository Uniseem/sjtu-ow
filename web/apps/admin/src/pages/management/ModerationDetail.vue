<script setup lang="ts">
import { ref,watch } from "vue"
import { useRoute } from "vue-router"
import { getApiAdminModerationId, postApiAdminModerationIdHandle, postApiAdminModerationIdAskAuthor } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useResource } from "./use-resource"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import { date,localHref } from "./format"
import { statusLabels,riskLabels,targetLabels,categories } from "./moderation-labels"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ActionState from "../../components/management/ActionState.vue"
const api=useAdminApi(),route=useRoute(),confirm=useConfirm()
const note=ref(''),message=ref(''),clearMotto=ref(false)
const resource=useResource(()=>route.params.id,signal=>getApiAdminModerationId(api,String(route.params.id),{signal}))
watch(resource.data,value=>{if(value?.item)note.value=value.item.handling_note})
const handle=useAdminAction<{action:string;note:string;clear_motto:boolean},unknown>((body,extras)=>postApiAdminModerationIdHandle(api,String(route.params.id),body,extras),()=>resource.refresh())
const ask=useAdminAction<{message:string},unknown>((body,extras)=>postApiAdminModerationIdAskAuthor(api,String(route.params.id),body,extras),()=>resource.refresh())
function askAuthor(){if(ask.canStart.value && confirm(`把这段说明发邮件给 ${resource.data.value?.item?.author_name||'作者'}？发出后这条记为「已处置」。`))void ask.submit({message:message.value})}
</script>
<template>
 <AdminPage :title="'复核内容'" section="审核" back-href="/admin/moderation/">
  <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
  <div v-if="resource.data.value?.item" class="b-split">
   <div class="b-form">
    <section class="b-section"><h2 class="b-section__title">送审内容</h2><div class="b-letter">{{ resource.data.value.item.excerpt }}</div></section>
    <section class="b-section"><h2 class="b-section__title">处理记录</h2><ul v-if="(resource.data.value.history_rows?.length ?? 0)" class="b-list"><li v-for="entry in resource.data.value.history_rows" :key="entry.id"><span>{{ date(entry.created_at) }} · {{ entry.actor_name }} · {{ statusLabels[entry.result] || entry.result }}</span><span class="b-sub">{{ entry.note }}</span></li></ul><p v-else class="b-section__text">还没有人处理过这条。</p></section>
    <section class="b-section"><h2 class="b-section__title">要求作者修改</h2><p v-if="resource.data.value.author_problem" class="b-section__text">{{ resource.data.value.author_problem }}</p><form v-else class="b-form" @submit.prevent="askAuthor"><div class="c-field"><label class="c-field__label" for="ask_message">写给作者的说明（会原样发出去）</label><textarea id="ask_message" v-model="message" name="message" rows="4" maxlength="500" required class="c-input" placeholder="比如：队名里有辱骂的词，请换一个。" /><div class="c-field__help">发给 {{ resource.data.value.item.author_name||'作者' }}。信里会附上这条内容的类型、片段和修改入口。</div></div><div class="b-actions"><button type="submit" class="c-btn c-btn--secondary" :disabled="!ask.canStart.value || !handle.canStart.value || !message.trim()">发信给作者</button></div></form><ActionState :message="ask.message.value" :pending="ask.pending.value" :uncertain="ask.uncertain.value" @retry="ask.retry" /></section>
    <section class="b-section"><h2 class="b-section__title">记录处理结果</h2><p class="b-section__text">这里只记录你做了什么。撤下文章、清空战队简介、停用账号等操作请到对应功能里执行——AI 和这个页面都不会替你改动内容。</p><form class="b-form" @submit.prevent><div class="c-field"><label class="c-field__label" for="handling_note">处理说明</label><input id="handling_note" v-model="note" name="handling_note" class="c-input" maxlength="300" /></div><label v-if="resource.data.value.item.target_type==='motto'" class="c-check"><input v-model="clearMotto" type="checkbox" />同时清空这条个人宣言</label><div class="b-actions"><button v-for="(label,value) in {ok:'标记为无问题',handled:'已处置',ignored:'忽略'}" :key="value" type="button" class="c-btn" :class="value==='ok'?'c-btn--primary':'c-btn--secondary'" :disabled="!handle.canStart.value || !ask.canStart.value" @click="handle.submit({action:value,note,clear_motto:clearMotto})">{{ label }}</button></div></form><ActionState :message="handle.message.value" :pending="handle.pending.value" :uncertain="handle.uncertain.value" @retry="handle.retry" /></section>
   </div>
   <aside class="b-aside"><section class="b-section"><dl class="b-kv">
    <dt>内容类型</dt><dd>{{ targetLabels[resource.data.value.item.target_type]||resource.data.value.item.target_label }}<template v-if="resource.data.value.item.field">（{{ resource.data.value.item.field }}）</template></dd><dt>风险等级</dt><dd>{{ riskLabels[resource.data.value.item.risk]||resource.data.value.item.risk }}</dd><dt>命中类别</dt><dd>{{ categories(resource.data.value.item.categories) }}</dd><dt>AI 理由</dt><dd>{{ resource.data.value.item.reason||'—' }}</dd><dt>引用原文</dt><dd>{{ resource.data.value.item.quote||'—' }}</dd><dt>作者</dt><dd>{{ resource.data.value.item.author_name||'—' }}（此前被标记 {{ resource.data.value.author_flags }} 次）</dd><dt>内容地址</dt><dd><a v-if="localHref(resource.data.value.item.url)" class="c-link" :href="localHref(resource.data.value.item.url)" target="_blank" rel="noopener">{{ resource.data.value.item.url }}</a><template v-else>—</template></dd><dt>模型</dt><dd>{{ resource.data.value.item.model || '—' }}</dd><dt>审核时间</dt><dd>{{ date(resource.data.value.item.checked_at) }}</dd><dt>当前状态</dt><dd>{{ statusLabels[resource.data.value.item.status]||resource.data.value.item.status }}<template v-if="resource.data.value.item.reviewer_name">（{{ resource.data.value.item.reviewer_name }}，{{ date(resource.data.value.item.reviewed_at) }}）</template></dd><template v-if="resource.data.value.item.handling_note"><dt>处理说明</dt><dd>{{ resource.data.value.item.handling_note }}</dd></template>
   </dl></section></aside>
  </div>
 </AdminPage>
</template>
