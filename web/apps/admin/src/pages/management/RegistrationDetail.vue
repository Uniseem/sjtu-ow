<script setup lang="ts">
import { ref } from "vue"
import { useRoute } from "vue-router"
import { postApiAdminRegistrationsIdApprove, postApiAdminRegistrationsIdReject, postApiAdminRegistrationsIdDissolve } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useResource } from "./use-resource"
import { getRegistration } from "./pending"
import { date, state } from "./format"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ActionState from "../../components/management/ActionState.vue"
import ConfirmAction from "../../components/management/ConfirmAction.vue"
const api = useAdminApi()
const route = useRoute()
const note = ref("")
const resource = useResource(() => route.params.id, signal => getRegistration(api, String(route.params.id), { signal }))
const action = useAdminAction<{ kind: 'approve' | 'reject' | 'dissolve'; note: string }, unknown>((body, extras) => {
  const id = String(route.params.id)
  if (body.kind === 'approve') return postApiAdminRegistrationsIdApprove(api, id, extras)
  if (body.kind === 'reject') return postApiAdminRegistrationsIdReject(api, id, { note: body.note }, extras)
  return postApiAdminRegistrationsIdDissolve(api, id, extras)
}, () => resource.refresh())
</script>
<template>
  <AdminPage :title="resource.data.value?.registration.team_name || '报名详情'" section="审核" back-href="/admin/registrations/">
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <div v-if="resource.data.value" class="b-split">
      <div class="b-form">
        <section class="b-section">
          <h2 class="b-section__title">报名时的名单</h2>
          <p class="b-section__text">以下为提交报名时的快照；当前资料的改动不会自动替换这份名单。</p>
          <p v-for="warning in resource.data.value.warnings" :key="warning" class="c-notice c-notice--warn">{{ warning }}</p>
          <table class="c-table">
            <thead>
              <tr>
                <th scope="col">成员</th>
                <th scope="col">游戏 ID</th>
                <th scope="col">段位</th>
                <th scope="col">交大</th>
                <th scope="col">联系方式</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="person in resource.data.value.roster" :key="person.id">
                <td>{{ person.nickname }}<span v-if="person.is_captain" class="c-tag">队长</span>
                  <span v-if="!person.is_active" class="b-sub">已停用</span>
                </td>
                <td class="b-mono">{{ person.battletag }}</td>
                <td>{{ person.ranks || '—' }}</td>
                <td>{{ person.is_sjtu ? '是' : '否' }}</td>
                <td>{{ person.contacts?.join('、') || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </section>
        <section class="b-section">
          <h2 class="b-section__title">操作记录</h2>
          <ul class="b-list">
            <li v-for="record in resource.data.value.logs" :key="record.id">
              <span>{{ record.action }} · {{ record.actor_name }}<span v-if="record.note" class="b-sub">{{ record.note }}</span>
              <span class="b-sub">名单第 {{ record.roster_version }} 版</span>
            </span>
            <time>{{ date(record.created_at) }}</time>
          </li>
        </ul>
        <p v-if="!resource.data.value.logs.length" class="b-sub">还没有操作记录。</p>
      </section>
    </div>
    <aside class="b-aside">
      <section class="b-section">
        <h2 class="b-section__title">报名</h2>
        <dl class="b-kv">
          <dt>赛事</dt>
          <dd>
            <RouterLink :to="`/admin/tournaments/edit/${resource.data.value.registration.tournament_id}/`">{{ resource.data.value.registration.tournament_title }}</RouterLink>
          </dd>
          <dt>状态</dt>
          <dd>{{ state(resource.data.value.registration.status) }}</dd>
          <dt>提交</dt>
          <dd>{{ date(resource.data.value.registration.submitted_at) }}</dd>
          <dt>说明</dt>
          <dd>{{ resource.data.value.registration.status_note || '—' }}</dd>
        </dl>
      </section>
      <section v-if="resource.data.value.registration.can_approve || resource.data.value.registration.can_reject || resource.data.value.registration.can_dissolve" class="b-section">
        <h2 class="b-section__title">处理报名</h2>
        <ConfirmAction v-if="resource.data.value.registration.can_approve" title="通过报名" message="通过这份报名？" label="通过" :pending="!action.canStart.value" @confirm="action.submit({ kind: 'approve', note: '' })" />
        <template v-if="resource.data.value.registration.can_reject">
          <label class="c-field__label" for="reject-note">驳回原因</label>
          <textarea id="reject-note" v-model="note" class="c-input" maxlength="1000" />
          <ConfirmAction title="驳回报名" message="驳回这份报名？" label="驳回" danger :pending="!action.canStart.value || !note.trim()" @confirm="action.submit({ kind: 'reject', note })" />
        </template>
        <ConfirmAction v-if="resource.data.value.registration.can_dissolve" title="撤销报名" message="撤销这份报名？名单和操作记录会保留。" label="撤销" danger :pending="!action.canStart.value" @confirm="action.submit({ kind: 'dissolve', note: '' })" />
        <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
      </section>
    </aside>
  </div>
  </AdminPage>
</template>
