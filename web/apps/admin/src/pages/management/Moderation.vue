<script setup lang="ts">
import { computed, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiAdminModeration } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import { positive, text, date, state, localHref } from "./format"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ManagementPager from "../../components/management/ManagementPager.vue"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const status = ref(text(route.query.status))
const risk = ref(text(route.query.risk))
const type = ref(text(route.query.target_type))
const resource = useResource(() => route.fullPath, signal => getApiAdminModeration(api, { status: text(route.query.status), risk: text(route.query.risk), target_type: text(route.query.target_type), page: positive(route.query.page) }, { signal }))
const rows = computed(() => (resource.data.value?.items ?? []).filter(item => item !== null))
function filter() { void router.push({ path: route.path, query: { status: status.value || undefined, risk: risk.value || undefined, target_type: type.value || undefined } }) }
</script>
<template>
  <AdminPage title="内容巡查" section="审核">
    <p class="b-section__text">巡查记录供人工复核参考。</p>
    <form class="b-filters" @submit.prevent="filter">
      <select v-model="status" class="c-input" aria-label="处理状态">
        <option value="">全部状态</option>
        <option value="unreviewed">未处理</option>
        <option value="reviewed">已处理</option>
        <option value="failed">巡查失败</option>
      </select>
      <select v-model="risk" class="c-input" aria-label="风险">
        <option value="">全部风险</option>
        <option value="high">高</option>
        <option value="medium">中</option>
        <option value="low">低</option>
      </select>
      <select v-model="type" class="c-input" aria-label="内容类型">
        <option value="">全部类型</option>
        <option value="article">文章</option>
        <option value="comment">评论</option>
        <option value="profile">成员资料</option>
      </select>
      <button class="c-btn c-btn--secondary c-btn--sm">筛选</button>
    </form>
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" :empty="!rows.length" empty-text="没有符合条件的巡查记录。" @retry="resource.refresh" />
    <p v-if="resource.data.value" class="b-sub">{{ resource.data.value.waiting }} 件等待巡查 · {{ resource.data.value.failed }} 件失败</p>
    <table v-if="rows.length" class="c-table">
      <thead>
        <tr>
          <th scope="col">内容</th>
          <th scope="col">风险</th>
          <th scope="col">判断</th>
          <th scope="col">状态</th>
          <th scope="col">时间</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in rows" :key="item.id">
          <td>
            <RouterLink class="b-title" :to="`/admin/moderation/${item.id}/`">{{ item.target_label }}</RouterLink>
            <span class="b-sub">{{ item.excerpt }}</span>
            <a v-if="localHref(item.url)" class="c-link" :href="localHref(item.url)" target="_blank" rel="noopener">看原内容 →</a>
          </td>
          <td>{{ state(item.risk) }}</td>
          <td>{{ item.reason }}<span class="b-sub">{{ item.categories.join('、') }}</span>
          </td>
          <td>{{ state(item.status) }}</td>
          <td>{{ date(item.checked_at || item.created_at) }}</td>
        </tr>
      </tbody>
    </table>
    <ManagementPager v-if="resource.data.value" :page="resource.data.value.page" :size="resource.data.value.page_size" :total="resource.data.value.total" />
  </AdminPage>
</template>
