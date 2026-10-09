<script setup lang="ts">
import { ref, onMounted } from "vue"
import { getApiAdminFeatureRoleRestrictions, type GetApiAdminFeatureRoleRestrictionsOut } from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"

const membersSection = ADMIN_SECTIONS.find((s) => s.id === "members")
const usersTab = membersSection?.tabs.find((t) => t.id === "users")

const loading = ref(true)
const restrictions = ref<GetApiAdminFeatureRoleRestrictionsOut["restrictions"]>([])
const error = ref<string | null>(null)

async function loadRestrictions() {
  loading.value = true
  try {
    const res = await getApiAdminFeatureRoleRestrictions()
    restrictions.value = res.restrictions
  } catch (err: any) {
    error.value = err?.message ?? "加载角色限制失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadRestrictions()
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
      active-subtab="roles"
    />

    <div class="b-main">
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <section class="b-section p-6 rounded-lg bg-surface border border-border shadow-xs">
        <h2 class="text-base font-bold text-fg mb-2">角色与功能限制规则</h2>
        <p class="text-xs text-fg-3 mb-6">
          可以针对特定用户组配置功能开关（如禁止某个组新建战队或报名内战）。
        </p>

        <div v-if="loading" class="text-center py-8 text-fg-3">正在拉取角色规则...</div>
        <div v-else-if="restrictions.length === 0" class="text-center py-8 text-fg-3 border border-dashed border-border rounded-lg">
          当前暂无任何角色功能限制规则，所有组按默认权限开放。
        </div>
        <div v-else class="space-y-3">
          <div
            v-for="r in restrictions"
            :key="`${r.role}-${r.feature}`"
            class="flex items-center justify-between p-3 rounded-md bg-surface-2 border border-border text-sm"
          >
            <div>
              <p class="font-bold text-fg">角色：{{ r.role }} · 限制功能：{{ r.feature }}</p>
              <p class="text-xs text-fg-3">说明：{{ r.reason || "无附加说明" }}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
