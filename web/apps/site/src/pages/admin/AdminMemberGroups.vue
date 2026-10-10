<script setup lang="ts">
import { ref, onMounted } from "vue"
import { getApiAdminMemberGroups, type GetApiAdminMemberGroupsOut } from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"
import { useApi } from "../../api"

const api = useApi()

const membersSection = ADMIN_SECTIONS.find((s) => s.id === "members")
const loading = ref(true)
const groups = ref<GetApiAdminMemberGroupsOut["groups"]>([])
const error = ref<string | null>(null)

async function loadGroups() {
  loading.value = true
  try {
    const res = await getApiAdminMemberGroups(api)
    groups.value = res.groups
  } catch (err: any) {
    error.value = err?.message ?? "加载成员分组失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadGroups()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="成员"
      title="成员分组管理"
      :tabs="membersSection?.tabs"
      active-tab="member_groups"
    >
      <template #actions>
        <button class="c-btn c-btn--primary c-btn--sm">
          <CIcon name="plus" class="size-4 mr-1" /> 新建分组
        </button>
      </template>
    </AdminHead>

    <div class="b-main">
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <div class="bg-surface border border-border rounded-lg overflow-x-auto">
        <table class="c-table w-full text-left">
          <thead>
            <tr class="border-b border-border text-xs text-fg-3">
              <th class="p-3 font-medium">分组名称</th>
              <th class="p-3 font-medium">排序权重</th>
              <th class="p-3 font-medium">公开可见</th>
              <th class="p-3 font-medium">成员人数</th>
              <th class="p-3 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" class="border-b border-border">
              <td colspan="5" class="p-8 text-center text-fg-3">正在拉取分组列表...</td>
            </tr>
            <tr v-else-if="groups.length === 0" class="border-b border-border">
              <td colspan="5" class="p-8 text-center text-fg-3">暂无成员分组</td>
            </tr>
            <tr
              v-for="g in groups"
              v-else
              :key="g.id"
              class="border-b border-border hover:bg-surface-2 transition-colors"
            >
              <td class="p-3 font-bold text-fg">{{ g.name || "（未命名分组）" }}</td>
              <td class="p-3 text-sm text-fg-2">{{ g.sort_order }}</td>
              <td class="p-3 text-sm">
                <span :class="g.visible ? 'text-success' : 'text-fg-3'">
                  {{ g.visible ? '显示' : '隐藏' }}
                </span>
              </td>
              <td class="p-3 text-sm text-fg-2">{{ g.member_count }} 人</td>
              <td class="p-3 text-right">
                <div class="inline-flex gap-2">
                  <button class="c-btn c-btn--ghost c-btn--xs">编辑与成员</button>
                  <button class="c-btn c-btn--ghost c-btn--xs text-danger">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
