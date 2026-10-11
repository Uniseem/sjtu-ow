<script setup lang="ts">
import { computed, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiAdminUsersSearch } from "@sjtu-ow/api"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ManagementPager from "../../components/management/ManagementPager.vue"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import { date, positive, text } from "./format"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const search = ref(text(route.query.q))
const role = ref(text(route.query.role))
const active = ref(text(route.query.active))
const sjtu = ref(text(route.query.sjtu))
const resource = useResource(() => route.fullPath, signal => getApiAdminUsersSearch(api, { q: text(route.query.q), role: text(route.query.role), active: text(route.query.active), sjtu: text(route.query.sjtu), page: positive(route.query.page) }, { signal }))
const rows = computed(() => resource.data.value?.users ?? [])
function roleLabel(name: string) { return resource.data.value?.roles.find(role => role.name === name)?.label || name }
function filter() { void router.push({ path: route.path, query: { q: search.value || undefined, role: role.value || undefined, active: active.value || undefined, sjtu: sjtu.value || undefined } }) }
</script>
<template>
  <AdminPage title="用户" section="成员">
    <nav class="b-subtabs" aria-label="用户与权限">
      <RouterLink to="/admin/users/" aria-current="page">用户</RouterLink>
      <RouterLink to="/admin/roles/">角色</RouterLink>
    </nav>
    <form class="b-filters" role="search" @submit.prevent="filter">
      <input v-model="search" class="c-input" type="search" placeholder="搜昵称或邮箱" aria-label="搜昵称或邮箱" />
      <select v-model="role" class="c-input" aria-label="角色">
        <option value="">全部角色</option>
        <option v-for="item in resource.data.value?.roles" :key="item.id" :value="item.name">{{ item.label || item.name }}</option></select>
        <select v-model="active" class="c-input" aria-label="账号状态">
          <option value="">全部状态</option>
          <option value="yes">在用</option>
          <option value="no">已停用</option>
        </select>
        <select v-model="sjtu" class="c-input" aria-label="是否交大">
          <option value="">全部用户</option>
          <option value="yes">交大用户</option>
          <option value="no">校外用户</option>
        </select>
        <button type="submit" class="c-btn c-btn--secondary c-btn--sm">筛选</button>
      </form>
      <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" :empty="rows.length === 0" empty-text="没有符合条件的用户。" @retry="resource.refresh" />
      <table v-if="rows.length" class="c-table">
        <thead>
          <tr>
            <th scope="col">昵称</th>
            <th scope="col">邮箱</th>
            <th scope="col">是否交大</th>
            <th scope="col">角色</th>
            <th scope="col">状态</th>
            <th scope="col">注册时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in rows" :key="user.id">
            <td>
              <RouterLink class="b-title" :to="`/admin/users/${user.id}/`">{{ user.nickname }}</RouterLink>
            </td>
            <td>{{ user.email }}<span v-if="!user.email_verified" class="b-sub">还没验证</span>
            </td>
            <td>{{ user.is_sjtu ? '是' : '否' }}</td>
            <td>{{ user.is_superuser ? '超级管理员' : user.roles.map(roleLabel).join('、') || '—' }}</td>
            <td>{{ user.is_active ? '在用' : '已停用' }}</td>
            <td>{{ date(user.created_at) }}</td>
          </tr>
        </tbody>
      </table>
      <ManagementPager v-if="resource.data.value" :total="resource.data.value.total" :page="positive(route.query.page)" :size="50" />
    </AdminPage>
</template>
