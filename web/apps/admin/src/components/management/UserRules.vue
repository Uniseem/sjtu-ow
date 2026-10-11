<script setup lang="ts">
import { ref } from "vue"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useResource } from "../../pages/management/use-resource"
import { getUserRules, addUserRule, deleteUserRule, type UserRulesPage } from "../../pages/management/pending"
import ResourceState from "./ResourceState.vue"
import ActionState from "./ActionState.vue"
import ConfirmAction from "./ConfirmAction.vue"
const props = defineProps<{ id: string }>()
const api = useAdminApi()
const feature = ref("")
const allowed = ref(false)
const note = ref("")
const resource = useResource(() => props.id, signal => getUserRules(api, props.id, { signal }))
const action = useAdminAction<{ kind: "add" | "delete"; feature: string; allowed: boolean; note: string; rule: number }, UserRulesPage>(
  (body, extras) => body.kind === "add" ? addUserRule(api, props.id, { feature: body.feature, allowed: body.allowed, note: body.note }, extras) : deleteUserRule(api, props.id, body.rule, extras),
  result => { resource.data.value = result; note.value = ""; feature.value = "" })
function label(key: string) { return resource.data.value?.features.find(item => item.key === key)?.label ?? key }
</script>
<template>
  <section class="b-section">
    <h2 class="b-section__title">功能规则</h2>
    <p class="b-section__text">只对这个人：单独禁止某项功能（比如评论），或者在他所在的组关掉时单独允许。</p>
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" @retry="resource.refresh" />
    <ul v-if="resource.data.value?.rules.length" class="b-list">
      <li v-for="rule in resource.data.value.rules" :key="rule.id">
        <span>
          <strong>{{ label(rule.feature) }}</strong>：{{ rule.allowed ? '单独允许' : '单独禁止' }}<span v-if="rule.note" class="b-sub">{{ rule.note }}</span>
        </span>
        <ConfirmAction title="删除功能规则" message="删掉这条规则？" label="删除" :pending="!action.canStart.value" @confirm="action.submit({ kind: 'delete', rule: rule.id, feature: '', allowed: false, note: '' })" />
      </li>
    </ul>
    <form v-if="resource.data.value" class="b-filters" @submit.prevent="action.submit({ kind: 'add', feature, allowed, note, rule: 0 })">
      <select v-model="feature" class="c-input" aria-label="功能" required>
        <option value="">选择功能</option>
        <option v-for="item in resource.data.value.features" :key="item.key" :value="item.key" :disabled="resource.data.value.rules.some(rule => rule.feature === item.key)">{{ item.label }}</option>
      </select>
      <select v-model="allowed" class="c-input" aria-label="允许或禁止">
        <option :value="true">单独允许</option>
        <option :value="false">单独禁止</option>
      </select>
      <input v-model="note" class="c-input" maxlength="200" placeholder="原因（只有管理员看得到）" aria-label="原因" />
      <button class="c-btn c-btn--secondary c-btn--sm" :disabled="!action.canStart.value || !feature">加一条</button>
    </form>
    <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
  </section>
</template>
