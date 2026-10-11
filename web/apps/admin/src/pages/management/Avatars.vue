<script setup lang="ts">
import { reactive, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiAdminAvatars, postApiAdminAvatarsIdTakeDown } from "@sjtu-ow/api"
import { imageUrl } from "@sjtu-ow/shared/media"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useResource } from "./use-resource"
import { positive, text, date, state } from "./format"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ActionState from "../../components/management/ActionState.vue"
import ConfirmAction from "../../components/management/ConfirmAction.vue"
import ManagementPager from "../../components/management/ManagementPager.vue"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const status = ref(text(route.query.status))
const notes = reactive<Record<number, string>>({})
const resource = useResource(() => route.fullPath, signal => getApiAdminAvatars(api, { status: text(route.query.status), page: positive(route.query.page), page_size: 48 }, { signal }))
const action = useAdminAction<{ id: number; note: string }, { result: string }>((body, extras) => postApiAdminAvatarsIdTakeDown(api, body.id, { note: body.note }, extras), () => resource.refresh())
function filter() { void router.push({ path: route.path, query: { status: status.value || undefined } }) }
</script>
<template>
  <AdminPage title="头像" section="审核">
    <form class="b-filters" @submit.prevent="filter">
      <select v-model="status" class="c-input" aria-label="状态">
        <option value="">全部</option>
        <option value="active">正常</option>
        <option value="taken_down">已撤下</option>
      </select>
      <button class="c-btn c-btn--secondary c-btn--sm">筛选</button>
    </form>
    <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" :empty="!resource.data.value?.items.length" empty-text="没有符合条件的头像。" @retry="resource.refresh" />
    <div class="b-grid">
      <article v-for="item in resource.data.value?.items" :key="item.id" class="b-grid__item">
        <img v-if="item.image_id" :src="imageUrl(item.image_id, 'fill-176x176')" :alt="`${item.user_nickname}的头像`" width="160" height="160" loading="lazy" />
        <a class="b-title" :href="`/members/${item.user_id}/`">{{ item.user_nickname }}</a>
        <p class="b-sub">{{ date(item.created_at) }} · {{ state(item.status) }}</p>
        <p v-if="item.handling_note" class="b-sub">{{ item.handling_note }}</p>
        <template v-if="item.status !== 'taken_down'">
          <label class="c-field__label" :for="`avatar-note-${item.id}`">撤下原因</label>
          <input :id="`avatar-note-${item.id}`" v-model="notes[item.id]" class="c-input" maxlength="200" />
          <ConfirmAction title="撤下头像" message="撤下这张头像？用户会恢复默认头像。" label="撤下" danger :pending="!action.canStart.value || !notes[item.id]?.trim()" @confirm="action.submit({ id: item.id, note: notes[item.id] || '' })" />
        </template>
      </article>
    </div>
    <ManagementPager v-if="resource.data.value" :page="resource.data.value.page" :size="resource.data.value.page_size" :total="resource.data.value.total" />
  </AdminPage>
</template>
