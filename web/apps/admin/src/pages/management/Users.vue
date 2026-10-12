<script setup lang="ts">
import { computed, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiAdminUsersSearch } from "@sjtu-ow/api"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ManagementPager from "../../components/management/ManagementPager.vue"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import { day, positive, text } from "./format"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const search = ref(text(route.query.q))
const role = ref(text(route.query.role))
const state = ref(text(route.query.state))
const sjtu = ref(text(route.query.sjtu))
const roleKeys: Record<string,string> = { '内容编辑':'content_editor', '认证作者':'certified_author', '赛事管理员':'tournament_admin', '内战管理员':'scrim_admin', '投稿者':'contributor', '交大用户':'sjtu_user', '校外用户':'external_user' }
const resource = useResource(() => route.fullPath, signal => getApiAdminUsersSearch(api, {
  q:text(route.query.q), role:roleKeys[text(route.query.role)] ?? text(route.query.role),
  active:text(route.query.state)==='active'?'yes':text(route.query.state)==='stopped'?'no':'',
  sjtu:text(route.query.sjtu)==='1'?'yes':text(route.query.sjtu)==='0'?'no':'', page:positive(route.query.page),
}, {signal}))
const rows = computed(() => resource.data.value?.users ?? [])
const roles = computed(() => [...(resource.data.value?.roles ?? [])].sort((a,b) => a.label < b.label ? -1 : a.label > b.label ? 1 : 0))
function roleLabel(name:string):string { return resource.data.value?.roles.find(role => role.name === name)?.label || name }
function visibleRoles(names:string[]):string[] { return names.filter(name => name !== 'sjtu_user' && name !== 'external_user').sort((a,b) => roleLabel(a) < roleLabel(b) ? -1 : roleLabel(a) > roleLabel(b) ? 1 : 0) }
function filter() { void router.push({path:route.path,query:{q:search.value||undefined,role:role.value||undefined,state:state.value||undefined,sjtu:sjtu.value||undefined}}) }
</script>
<template>
  <AdminPage title="用户" section="成员">
    <template #subtabs><nav class="b-subtabs" aria-label="用户与权限"><RouterLink to="/admin/users/" aria-current="page">用户</RouterLink><RouterLink to="/admin/roles/">角色</RouterLink></nav></template>
    <form method="get" class="b-filters" role="search" @submit.prevent="filter">
      <input v-model="search" type="search" name="q" maxlength="50" placeholder="搜昵称或邮箱" class="c-input" aria-label="搜用户">
      <select v-model="role" name="role" class="c-input" aria-label="角色" @change="filter"><option value="">全部角色</option><option v-for="item in roles" :key="item.id" :value="item.label">{{ item.label }}</option></select>
      <select v-model="state" name="state" class="c-input" aria-label="状态" @change="filter"><option value="">在用和已停用</option><option value="active">在用</option><option value="stopped">已停用</option></select>
      <select v-model="sjtu" name="sjtu" class="c-input" aria-label="是否交大" @change="filter"><option value="">交大和校外</option><option value="1">交大</option><option value="0">校外</option></select>
      <button type="submit" class="c-btn c-btn--secondary c-btn--sm">筛选</button><span class="b-count">{{ resource.data.value?.total ?? 0 }} 人</span>
    </form>
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <table v-if="rows.length" class="c-table c-table--stack">
      <thead><tr><th>昵称</th><th>邮箱</th><th>交大</th><th>角色</th><th>状态</th><th>注册</th></tr></thead>
      <tbody><tr v-for="user in rows" :key="user.id" :data-user-row="user.id">
        <td><RouterLink class="b-title" :to="'/admin/users/' + user.id + '/'">{{ user.nickname || '（没有昵称）' }}</RouterLink><span v-if="user.is_superuser" class="b-sub">超级管理员</span></td>
        <td data-label="邮箱">{{ user.email }}</td><td data-label="交大">{{ user.is_sjtu ? '是' : '否' }}</td>
        <td data-label="角色"><template v-for="name in visibleRoles(user.roles)" :key="name"><span class="c-tag">{{ roleLabel(name) }}</span>{{ ' ' }}</template><template v-if="!user.roles.length">—</template></td>
        <td data-label="状态"><CStatus :label="user.is_active ? '在用' : '已停用'" :kind="user.is_active ? 'ok' : 'off'" /></td>
        <td data-label="注册">{{ day(user.created_at) }}</td>
      </tr></tbody>
    </table>
    <CEmpty v-else-if="!resource.pending.value && !resource.message.value" title="没有这样的用户" message="换个筛选条件试试。" />
    <ManagementPager v-if="resource.data.value" :total="resource.data.value.total" :page="positive(route.query.page)" :size="50" />
  </AdminPage>
</template>
