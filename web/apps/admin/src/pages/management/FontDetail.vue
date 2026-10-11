<script setup lang="ts">
import { useRoute, useRouter } from "vue-router"
import { getFont, deleteFont } from "./pending"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useResource } from "./use-resource"
import { date } from "./format"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ActionState from "../../components/management/ActionState.vue"
import ConfirmAction from "../../components/management/ConfirmAction.vue"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const resource = useResource(() => route.params.id, signal => getFont(api, String(route.params.id), { signal }))
const remove = useAdminAction<number, { result: string }>((id, extras) => deleteFont(api, id, extras), async () => { await router.push('/admin/settings/fonts/') })
</script>
<template>
  <AdminPage :title="resource.data.value?.font.display_name || '字体'" section="设置" back-href="/admin/settings/fonts/">
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <template v-if="resource.data.value">
      <section class="b-section">
        <h2 class="b-section__title">字体信息</h2>
        <dl class="b-kv">
          <dt>家族名称</dt>
          <dd>{{ resource.data.value.font.family }}</dd>
          <dt>来源</dt>
          <dd>{{ resource.data.value.font.source }}</dd>
          <dt>授权</dt>
          <dd>{{ resource.data.value.font.license || '—' }}</dd>
          <dt>状态</dt>
          <dd>{{ resource.data.value.font.status }}</dd>
          <dt>加入</dt>
          <dd>{{ date(resource.data.value.font.created_at) }}</dd>
          <dt>正在使用</dt>
          <dd>{{ resource.data.value.font.used_by.join('、') || '未使用' }}</dd>
        </dl>
        <p v-if="resource.data.value.font.error" class="c-field__error" role="alert">{{ resource.data.value.font.error }}</p>
      </section>
      <section class="b-section">
        <h2 class="b-section__title">字重和分片</h2>
        <table class="c-table">
          <thead>
            <tr>
              <th scope="col">字重</th>
              <th scope="col">分片</th>
              <th scope="col">字节</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="slice in resource.data.value.slices" :key="`${slice.weight}:${slice.style}`">
              <td>{{ slice.weight }}{{ slice.style === 'italic' ? ' 斜体' : '' }}<span class="b-sub">{{ slice.status || '' }}</span><span v-if="slice.error" class="c-field__error">{{ slice.error }}</span></td>
              <td>{{ slice.files }}</td>
              <td>{{ slice.bytes }}</td>
            </tr>
          </tbody>
        </table>
      </section>
      <ConfirmAction v-if="resource.data.value.font.can_delete" title="删除字体" message="删除这份字体和全部分片？" label="删除字体" danger :pending="!remove.canStart.value" @confirm="remove.submit(resource.data.value!.font.id)" />
      <p v-else class="b-sub">正在使用的字体不能删除。先在排版设置里更换字体。</p>
    </template>
    <ActionState :message="remove.message.value" :pending="remove.pending.value" :uncertain="remove.uncertain.value" @retry="remove.retry" />
  </AdminPage>
</template>
