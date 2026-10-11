<script setup lang="ts">
import { getFonts, deleteFont } from "./pending"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useResource } from "./use-resource"
import { date } from "./format"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ActionState from "../../components/management/ActionState.vue"
import ConfirmAction from "../../components/management/ConfirmAction.vue"
const api = useAdminApi()
const resource = useResource(() => true, signal => getFonts(api, { signal }))
const remove = useAdminAction<number, { result: string }>((id, extras) => deleteFont(api, id, extras), () => resource.refresh())
function bytes(value: number) { return value < 1024 ? `${value} B` : value < 1024 * 1024 ? `${(value / 1024).toFixed(1)} KB` : `${(value / 1024 / 1024).toFixed(1)} MB` }
</script>
<template>
  <AdminPage title="字体库" section="设置">
    <template #actions>
      <RouterLink to="/admin/settings/fonts/add/" class="c-btn c-btn--primary c-btn--sm">添加字体</RouterLink>
      <RouterLink to="/admin/settings/typography/" class="c-btn c-btn--secondary c-btn--sm">排版设置</RouterLink>
    </template>
    <p class="b-section__text">字体下载或上传后保存在本站，前台使用本站副本。</p>
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" :empty="!resource.data.value?.fonts.length" empty-text="还没有字体，全站使用系统字体。" @retry="resource.refresh" />
    <ActionState :message="remove.message.value" :pending="remove.pending.value" :uncertain="remove.uncertain.value" @retry="remove.retry" />
    <table v-if="resource.data.value?.fonts.length" class="c-table">
      <thead>
        <tr>
          <th scope="col">字体</th>
          <th scope="col">字重</th>
          <th scope="col">来源</th>
          <th scope="col">体积</th>
          <th scope="col">使用</th>
          <th scope="col">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="font in resource.data.value.fonts" :key="font.id">
          <td>
            <RouterLink class="b-title" :to="`/admin/settings/fonts/${font.id}/`">{{ font.display_name || font.family }}</RouterLink>
            <span class="b-sub">{{ date(font.created_at) }}</span>
            <span v-if="font.error" class="c-field__error">{{ font.error }}</span>
          </td>
          <td>{{ font.weights.join('、') || '—' }}</td>
          <td>{{ font.source }}</td>
          <td>{{ bytes(font.bytes) }} · {{ font.slices }} 个分片</td>
          <td>{{ font.used_by.join('、') || '未使用' }}</td>
          <td>
            <ConfirmAction v-if="font.can_delete" title="删除字体" :message="`删除字体「${font.display_name || font.family}」及其分片？`" label="删除" danger :pending="!remove.canStart.value" @confirm="remove.submit(font.id)" />
            <span v-else class="b-sub">正在使用，不能删除</span>
          </td>
        </tr>
      </tbody>
    </table>
  </AdminPage>
</template>
