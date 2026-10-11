<script setup lang="ts">
import { useRoute } from "vue-router"
import { getApiAdminModerationId } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import { date, state, localHref } from "./format"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
const api = useAdminApi()
const route = useRoute()
const resource = useResource(() => route.params.id, signal => getApiAdminModerationId(api, String(route.params.id), { signal }))
</script>
<template>
  <AdminPage :title="resource.data.value?.item?.target_label || '巡查记录'" section="审核" back-href="/admin/moderation/">
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <div v-if="resource.data.value?.item" class="b-split">
      <div class="b-form">
        <section class="b-section">
          <h2 class="b-section__title">巡查时的内容</h2>
          <p class="whitespace-pre-wrap">{{ resource.data.value.item.full_text || resource.data.value.item.excerpt }}</p>
          <a v-if="localHref(resource.data.value.item.url)" class="c-link" :href="localHref(resource.data.value.item.url)" target="_blank" rel="noopener">看原内容 →</a>
        </section>
        <section class="b-section">
          <h2 class="b-section__title">判断</h2>
          <dl class="b-kv">
            <dt>风险</dt>
            <dd>{{ state(resource.data.value.item.risk) }}</dd>
            <dt>分类</dt>
            <dd>{{ resource.data.value.item.categories.join('、') || '—' }}</dd>
            <dt>原因</dt>
            <dd>{{ resource.data.value.item.reason || '—' }}</dd>
            <dt>摘录</dt>
            <dd>{{ resource.data.value.item.quote || '—' }}</dd>
          </dl>
        </section>
        <section class="b-section">
          <h2 class="b-section__title">操作记录</h2>
          <ul class="b-list">
            <li v-for="record in resource.data.value.history" :key="record.id">
              <span>{{ record.action }}</span>
              <time>{{ date(record.created_at) }}</time>
            </li>
          </ul>
          <p v-if="!resource.data.value.history.length" class="b-sub">还没有操作记录。</p>
        </section>
      </div>
      <aside class="b-aside">
        <section class="b-section">
          <h2 class="b-section__title">状态</h2>
          <dl class="b-kv">
            <dt>处理</dt>
            <dd>{{ state(resource.data.value.item.status) }}</dd>
            <dt>巡查</dt>
            <dd>{{ date(resource.data.value.item.checked_at) }}</dd>
            <dt>复核</dt>
            <dd>{{ date(resource.data.value.item.reviewed_at) }}</dd>
            <dt>处理说明</dt>
            <dd>{{ resource.data.value.item.handling_note || '—' }}</dd>
            <dt>尝试次数</dt>
            <dd>{{ resource.data.value.item.attempts }}</dd>
          </dl>
          <p v-if="resource.data.value.item.last_error" class="c-field__error">{{ resource.data.value.item.last_error }}</p>
        </section>
        <section v-if="resource.data.value.author_problem" class="b-section">
          <h2 class="b-section__title">作者</h2>
          <p>{{ resource.data.value.author_problem }}</p>
        </section>
      </aside>
    </div>
  </AdminPage>
</template>
