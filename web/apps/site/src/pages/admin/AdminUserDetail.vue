<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRoute } from "vue-router"
import { getApiAdminUsersId, type GetApiAdminUsersIdOut } from "@sjtu-ow/api"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"
import { useApi } from "../../api"

const api = useApi()

const route = useRoute()
const id = ref((route.params.id as string) || "")
const loading = ref(true)
const user = ref<GetApiAdminUsersIdOut["user"] | null>(null)
const error = ref<string | null>(null)

async function loadUser() {
  loading.value = true
  try {
    const res = await getApiAdminUsersId(api, id.value)
    user.value = res.user
  } catch (err: any) {
    error.value = err?.message ?? "加载用户详情失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadUser()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="成员"
      :title="user ? `${user.nickname} · 用户权限详情` : '用户权限详情'"
      back-to="/admin/users/"
      back-label="返回用户列表"
    />

    <div class="b-main">
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <div class="b-split grid grid-cols-1 lg:grid-cols-[1fr_22rem] gap-6">
        <!-- 用户主信息与功能规则 -->
        <div class="flex flex-col gap-6">
          <div class="bg-surface p-6 rounded-lg border border-border shadow-xs">
            <h2 class="font-bold text-base text-fg mb-4 pb-2 border-b border-border">基本档案</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <span class="text-xs text-fg-3 block">昵称</span>
                <span class="font-bold text-fg">{{ user?.nickname }}</span>
              </div>
              <div>
                <span class="text-xs text-fg-3 block">注册邮箱</span>
                <span class="font-mono text-fg">{{ user?.email }}</span>
              </div>
              <div>
                <span class="text-xs text-fg-3 block">交大在读</span>
                <span>{{ user?.is_sjtu ? '是' : '否' }}</span>
              </div>
              <div>
                <span class="text-xs text-fg-3 block">账号状态</span>
                <span :class="user?.is_active ? 'text-success font-medium' : 'text-danger font-medium'">
                  {{ user?.is_active ? '正常使用中' : '已停用' }}
                </span>
              </div>
            </div>
          </div>

          <div class="bg-surface p-6 rounded-lg border border-border shadow-xs">
            <h2 class="font-bold text-base text-fg mb-4 pb-2 border-b border-border">赋予的角色</h2>
            <div class="flex flex-wrap gap-2">
              <span
                v-for="r in (user?.roles ?? [])"
                :key="r"
                class="px-2.5 py-1 rounded bg-surface-2 border border-border text-xs font-medium text-fg"
              >
                {{ r }}
              </span>
              <span v-if="!user?.roles?.length" class="text-xs text-fg-3">未分配任何特定角色（普通成员权限）</span>
            </div>
          </div>
        </div>

        <!-- 右侧操作 -->
        <aside class="b-aside flex flex-col gap-4">
          <div class="b-section p-5 rounded-lg bg-surface border border-border shadow-xs">
            <h3 class="font-bold text-sm mb-3 pb-2 border-b border-border">账号状态管理</h3>
            <div class="space-y-2">
              <button v-if="user?.is_active" class="c-btn c-btn--secondary w-full c-btn--sm text-danger">
                停用该账号
              </button>
              <button v-else class="c-btn c-btn--primary w-full c-btn--sm">
                启用该账号
              </button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>
