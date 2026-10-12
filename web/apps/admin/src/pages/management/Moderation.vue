<script setup lang="ts">
import { computed, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiAdminModeration } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import { positive,text,date } from "./format"
import { statusLabels,riskLabels,targetLabels,categories } from "./moderation-labels"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ManagementPager from "../../components/management/ManagementPager.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
const api=useAdminApi(),route=useRoute(),router=useRouter()
const status=ref(route.query.status===undefined?'pending':text(route.query.status)),risk=ref(text(route.query.risk)),type=ref(text(route.query.target_type)),since=ref(text(route.query.since))
const resource=useResource(()=>route.fullPath,signal=>getApiAdminModeration(api,{all:route.query.status==='',status:route.query.status===undefined?'pending':text(route.query.status),risk:text(route.query.risk),target_type:text(route.query.target_type),since:route.query.since?positive(route.query.since):undefined,page:positive(route.query.page)},{signal}))
const rows=computed(()=>(resource.data.value?.items??[]).filter(item=>item!==null))
function filter(){void router.push({path:route.path,query:{status:status.value,risk:risk.value||undefined,target_type:type.value||undefined,since:since.value||undefined}})}
</script>
<template>
 <AdminPage title="巡查记录" section="审核">
  <div class="c-notice c-notice--warn"><CIcon name="alert" /><div class="c-notice__body">AI 巡查引擎将在割接后移植，已有记录仍可查看、人工记录处理结果。</div></div>
  <section class="b-section"><p class="b-section__text">AI 每 30 分钟巡查一次新写或改过的内容，觉得可能不妥的会发信提醒（收件人在「设置 → 全站设置 → AI 审核」里填，没填发给超级管理员）。网站默认信任所有人，这里的记录是给你查的，标不标处理结果都行。<strong>AI 只做判断，不会改动任何内容。</strong></p></section>
  <form method="get" class="b-filters" @submit.prevent="filter">
   <select v-model="status" name="status" class="c-input" aria-label="状态" @change="filter"><option value="">全部状态</option><option v-for="(label,value) in statusLabels" :key="value" :value="value">{{ label }}</option></select>
   <select v-model="risk" name="risk" class="c-input" aria-label="风险" @change="filter"><option value="">全部风险</option><option v-for="(label,value) in riskLabels" :key="value" :value="value">{{ label }}</option></select>
   <select v-model="type" name="target_type" class="c-input" aria-label="类型" @change="filter"><option value="">全部类型</option><option v-for="(label,value) in targetLabels" :key="value" :value="value">{{ label }}</option></select>
   <select v-model="since" name="since" class="c-input" aria-label="提交时间" @change="filter"><option value="">全部时间</option><option value="1">最近 24 小时</option><option value="7">最近 7 天</option><option value="30">最近 30 天</option></select><button type="submit" class="c-btn c-btn--secondary c-btn--sm">筛选</button>
  </form>
  <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
  <table v-if="resource.data.value" class="c-table c-table--stack"><thead><tr><th>内容</th><th>风险</th><th>类别</th><th>类型</th><th>作者</th><th>时间</th><th>状态</th></tr></thead><tbody><tr v-for="item in rows" :key="item.id"><td><RouterLink class="b-title" :to="`/admin/moderation/${item.id}/`">{{ item.excerpt.length>60?item.excerpt.slice(0,59)+'…':item.excerpt }}</RouterLink></td><td data-label="风险">{{ riskLabels[item.risk]||item.risk }}</td><td data-label="类别">{{ categories(item.categories) }}</td><td data-label="类型">{{ targetLabels[item.target_type]||item.target_label }}</td><td data-label="作者">{{ item.author_name||'—' }}</td><td data-label="时间">{{ date(item.created_at) }}</td><td data-label="状态">{{ statusLabels[item.status]||item.status }}</td></tr><tr v-if="!rows.length"><td colspan="7">没有符合条件的记录。</td></tr></tbody></table>
  <ManagementPager v-if="resource.data.value" :page="resource.data.value.page" :size="resource.data.value.page_size" :total="resource.data.value.total" />
 </AdminPage>
</template>
