<script setup lang="ts">
import { computed, reactive } from "vue"
import { useRoute } from "vue-router"
import { getApiAdminAvatars, postApiAdminAvatarsIdTakeDown } from "@sjtu-ow/api"
import { imageUrl } from "@sjtu-ow/shared/media"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useResource } from "./use-resource"
import { positive, text } from "./format"
import { timestamp } from "../activities/domain"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ActionState from "../../components/management/ActionState.vue"
import ManagementPager from "../../components/management/ManagementPager.vue"
const api = useAdminApi()
const route = useRoute()
const notes = reactive<Record<number, string>>({})
const reasons = reactive<Record<number, string>>({})
const statuses = [{ value: "approved", label: "已通过" }, { value: "taken_down", label: "已撤下" }, { value: "rejected", label: "未通过" }]
const choices = [{value:"illegal",label:"违法违规"},{value:"porn",label:"色情低俗"},{value:"attack",label:"人身攻击"},{value:"politics",label:"政治敏感"},{value:"scam",label:"广告与诈骗"},{value:"game_trade",label:"游戏违规交易"},{value:"privacy",label:"泄露他人隐私"},{value:"impersonation",label:"冒充官方"},{value:"other",label:"其他可疑"}]
const status = computed(() => statuses.some((item) => item.value === route.query.status) ? text(route.query.status) : "approved")
const statusLabel = computed(() => statuses.find((item) => item.value === status.value)?.label ?? "已通过")
const resource = useResource(() => route.fullPath, signal => getApiAdminAvatars(api, { status: status.value, page: positive(route.query.page), page_size: 24 }, { signal }))
const action = useAdminAction<{ id: number; reason: string; note: string }, { result: string }>((body, extras) => postApiAdminAvatarsIdTakeDown(api, body.id, { reason: body.reason, note: body.note }, extras), () => resource.refresh())
</script>
<template>
  <AdminPage title="头像" section="审核">
    <p class="b-section__text">成员上传的头像马上就换上（网站默认信任所有人），这里按上传时间列出，最新的在前；看到不合适的就撤下，图片会删掉，并发信告诉本人原因。图片已经在服务器上裁成正方形，看到的就是显示的样子。</p>
    <nav class="b-chips" aria-label="状态">
      <RouterLink v-for="tab in statuses" :key="tab.value" :to="`?status=${tab.value}`" :aria-current="status === tab.value ? 'true' : undefined">{{ tab.label }}<span class="c-tabs__count">{{ resource.data.value?.counts[tab.value] ?? 0 }}</span></RouterLink>
    </nav>
    <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <ul class="avatar-review">
      <li v-for="item in resource.data.value?.items" :key="item.id" class="avatar-review__item">
        <div class="avatar-review__picture">
          <img v-if="item.image_id" :src="imageUrl(item.image_id, 'fill-240x240')" alt="" width="240" height="240" loading="lazy" />
          <span v-else class="b-sub">图片已删除</span>
        </div>
        <div class="avatar-review__body">
          <p><strong>{{ item.user_nickname }}</strong>{{ !item.user_active ? '（账号已停用）' : '' }}</p>
          <p class="b-sub">{{ timestamp(item.created_at) }} 上传<span v-if="item.turned_down"> · 之前被撤下 {{ item.turned_down }} 次</span></p>
          <p v-if="item.reviewed_by" class="b-sub">{{ statuses.find(tab => tab.value === item.status)?.label ?? item.status }}：{{ item.reviewer_nickname || '—' }}，{{ timestamp(item.reviewed_at) }}<span v-if="item.reason">；原因：{{ item.reason_display }}</span><span v-if="item.note">（{{ item.note }}）</span></p>
          <p v-if="item.status === 'approved' && item.is_current" class="b-sub">正在使用</p>
          <form v-if="item.status === 'approved' && item.image_id && item.is_current" class="avatar-review__form" @submit.prevent="action.submit({id:item.id,reason:reasons[item.id] || '',note:notes[item.id] || ''})">
            <select v-model="reasons[item.id]" name="reason" required class="c-input" aria-label="撤下的原因" :disabled="!action.canStart.value">
              <option value="">撤下的原因</option>
              <option v-for="choice in choices" :key="choice.value" :value="choice.value">{{ choice.label }}</option>
            </select>
            <input v-model="notes[item.id]" type="text" name="note" maxlength="200" class="c-input" placeholder="说明（可不填）" aria-label="说明" :disabled="!action.canStart.value" />
            <button type="submit" class="c-btn c-btn--danger c-btn--sm" :disabled="!action.canStart.value">撤下</button>
          </form>
        </div>
      </li>
      <li v-if="resource.data.value && !resource.data.value.items.length" class="b-section__text">没有{{ statusLabel }}的头像。</li>
    </ul>
    <ManagementPager v-if="resource.data.value" :page="resource.data.value.page" :size="resource.data.value.page_size" :total="resource.data.value.total" />
  </AdminPage>
</template>
