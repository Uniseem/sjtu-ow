<script setup lang="ts">
import { ref, onMounted } from "vue"
import { getApiAdminUsers, type GetApiAdminUsersOut } from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"

const membersSection = ADMIN_SECTIONS.find((s) => s.id === "members")
const usersTab = membersSection?.tabs.find((t) => t.id === "users")

const loading = ref(true)
const users = ref<GetApiAdminUsersOut["users"]>([])
const error = ref<string | null>(null)
const search = ref("")

async function loadUsers() {
  loading.value = true
  try {
    const res = await getApiAdminUsers()
    users.value = res.users
  } catch (err: any) {
    error.value = err?.message ?? "加载用户列表失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadUsers()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="成员"
      title="用户与权限"
      :tabs="membersSection?.tabs"
      active-tab="users"
      :subtabs="usersTab?.subtabs"
      active-subtab="users"
    />

    <div class="b-main">
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <div class="b-filters flex flex-wrap items-center gap-3 p-3 bg-surface border border-border rounded-lg">
        <div class="flex-1 min-w-[200px]">
          <input
            v-model="search"
            type="search"
            class="c-input w-full"
            placeholder="搜索昵称或邮箱..."
          />
        </div>
        <button class="c-btn c-btn--secondary c-btn--sm" @click="loadUsers">刷新</button>
      </div>

      <div class="bg-surface border border-border rounded-lg overflow-x-auto">
        <table class="c-table w-full text-left">
          <thead>
            <tr class="border-b border-border text-xs text-fg-3">
              <th class="p-3 font-medium">昵称</th>
              <th class="p-3 font-medium">邮箱</th>
              <th class="p-3 font-medium">交大在读</th>
              <th class="p-3 font-medium">角色与权限</th>
              <th class="p-3 font-medium">状态</th>
              <th class="p-3 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" class="border-b border-border">
              <td colspan="6" class="p-8 text-center text-fg-3">正在拉取用户列表...</td>
            </tr>
            <tr v-else-if="users.length === 0" class="border-b border-border">
              <td colspan="6" class="p-8 text-center text-fg-3">暂无匹配用户</td>
            </tr>
            <tr
              v-for="u in users"
              v-else
              :key="u.id"
              class="border-b border-border hover:bg-surface-2 transition-colors"
            >
              <td class="p-3 font-bold text-fg">
                <a :href="`/admin/users/${u.id}/`" class="hover:underline">{{ u.nickname }}</a>
                <span v-if="u.is_superuser" class="ml-1 text-[10px] bg-primary text-white px-1.5 py-0.5 rounded font-normal">超管</span>
              </td>
              <td class="p-3 font-mono text-xs text-fg-2">{{ u.email }}</td>
              <td class="p-3 text-sm">
                <span :class="u.is_sjtu ? 'text-success font-medium' : 'text-fg-3'">
                  {{ u.is_sjtu ? '是' : '否' }}
                </span>
              </td>
              <td class="p-3 text-xs text-fg-2">
                {{ u.roles?.join(', ') || '普通成员' }}
              </td>
              <td class="p-3 text-sm">
                <span
                  class="inline-block px-2 py-0.5 rounded text-xs"
                  :class="u.is_active ? 'bg-success-soft text-on-success-soft' : 'bg-danger-soft text-on-danger-soft'"
                >
                  {{ u.is_active ? '正常' : '已停用' }}
                </span>
              </td>
              <td class="p-3 text-right">
                <a :href="`/admin/users/${u.id}/`" class="c-btn c-btn--ghost c-btn--xs">详情与权限</a>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
