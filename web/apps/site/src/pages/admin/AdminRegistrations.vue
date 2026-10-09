<script setup lang="ts">
import { ref } from "vue"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"

const reviewSection = ADMIN_SECTIONS.find((s) => s.id === "review")
</script>

<template>
  <div>
    <AdminHead
      kicker="审核"
      title="赛事报名审核"
      :tabs="reviewSection?.tabs"
      active-tab="registrations"
    />

    <div class="b-main">
      <section class="b-section p-6 rounded-lg bg-surface border border-border shadow-xs text-center py-12">
        <CIcon name="trophy" class="size-10 mx-auto text-accent mb-3" />
        <h2 class="text-base font-bold text-fg mb-1">全部赛事报名审核</h2>
        <p class="text-xs text-fg-3 mb-6">
          你可以在各场赛事的详情页中直接点击「审核」进入专属审核面板，或在此批量查看最新待办。
        </p>
        <a href="/admin/tournaments/" class="c-btn c-btn--primary c-btn--sm">
          前往赛事管理列表
        </a>
      </section>
    </div>
  </div>
</template>
