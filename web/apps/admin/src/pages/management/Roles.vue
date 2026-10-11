<script setup lang="ts">
import { reactive } from "vue"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ActionState from "../../components/management/ActionState.vue"
import ConfirmAction from "../../components/management/ConfirmAction.vue"
import { getRoles, addRestriction, deleteRestriction, type RolesPage } from "./pending"
import { useResource } from "./use-resource"
const api = useAdminApi()
const forms = reactive<Record<number, { feature: string; note: string }>>({})
const resource = useResource(() => true, signal => getRoles(api, { signal }))
function form(id: number) { return forms[id] ?? (forms[id] = { feature: "", note: "" }) }
const action = useAdminAction<{ kind: "add" | "delete"; id: number; feature: string; note: string; rule: number }, RolesPage>(
  (body, extras) => body.kind === "add" ? addRestriction(api, body.id, { feature: body.feature, note: body.note }, extras) : deleteRestriction(api, body.id, body.rule, extras),
  result => { resource.data.value = result; for (const id of Object.keys(forms)) forms[Number(id)] = { feature: "", note: "" } })
function label(key: string) { return resource.data.value?.features.find(feature => feature.key === key)?.label ?? key }
</script>
<template>
  <AdminPage title="角色" section="成员">
    <nav class="b-subtabs" aria-label="用户与权限">
      <RouterLink to="/admin/users/">用户</RouterLink>
      <RouterLink to="/admin/roles/" aria-current="page">角色</RouterLink>
    </nav>
    <p class="b-section__text">谁在哪个角色里，在「用户」里编辑那个人。角色本身能做什么是固定的；细粒度的权限在底层后台的用户组里，平时不用动。</p>
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
    <section v-for="group in resource.data.value?.groups" :key="group.id" class="b-section" :data-role="group.name">
      <div class="c-panel__head">
        <h2 class="b-section__title">{{ group.label || group.name }}</h2>
        <RouterLink class="c-link" :to="{ path: '/admin/users/', query: { role: group.name } }">{{ group.people }} 人 →</RouterLink>
      </div>
      <p class="b-section__text">{{ group.summary }}</p>
      <ul v-if="group.restrictions.length" class="b-list">
        <li v-for="rule in group.restrictions" :key="rule.id">
          <span>关掉了<strong>{{ label(rule.feature) }}</strong>
            <span v-if="rule.note" class="b-sub">{{ rule.note }}</span>
          </span>
          <ConfirmAction title="打开功能" message="重新打开这项功能？" label="重新打开" :pending="!action.canStart.value" @confirm="action.submit({ kind: 'delete', id: group.id, rule: rule.id, feature: '', note: '' })" />
        </li>
      </ul>
      <form class="b-filters" @submit.prevent="action.submit({ kind: 'add', id: group.id, rule: 0, ...form(group.id) })">
        <select v-model="form(group.id).feature" class="c-input" aria-label="功能" required>
          <option value="">选择功能</option>
          <option v-for="feature in resource.data.value?.features" :key="feature.key" :value="feature.key" :disabled="group.restrictions.some(rule => rule.feature === feature.key)">{{ feature.label }}</option>
        </select>
        <input v-model="form(group.id).note" class="c-input" maxlength="200" aria-label="原因" placeholder="原因" />
        <button class="c-btn c-btn--secondary c-btn--sm" :disabled="!action.canStart.value || !form(group.id).feature">对这组关掉</button>
      </form>
    </section>
  </AdminPage>
</template>
