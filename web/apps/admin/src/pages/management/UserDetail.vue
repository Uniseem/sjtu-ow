<script setup lang="ts">
import { useRoute } from "vue-router"
import { getAdminUser } from "./pending"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import UserEditor from "../../components/management/UserEditor.vue"
import UserRules from "../../components/management/UserRules.vue"
import { useResource } from "./use-resource"
import { useAdminApi } from "../../core/api"
import { date } from "./format"
const api = useAdminApi()
const route = useRoute()
const resource = useResource(() => route.params.id, signal => getAdminUser(api, String(route.params.id), { signal }))
</script>
<template>
  <AdminPage :title="resource.data.value?.user?.Nickname || '用户'" section="成员" back-href="/admin/users/">
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <div v-if="resource.data.value?.user" class="b-split">
      <div class="b-form">
        <UserEditor :key="`${resource.data.value.user.ID}:${resource.data.value.user.IsActive}:${resource.data.value.roles.join(',')}`" :data="resource.data.value" @changed="resource.refresh" />
        <UserRules :key="resource.data.value.user.ID" :id="String(resource.data.value.user.ID)" />
      </div>
      <aside class="b-aside" aria-label="这个人在网站上">
        <section class="b-section">
          <h2 class="b-section__title">账号</h2>
          <dl class="b-kv">
            <dt>邮箱</dt>
            <dd>{{ resource.data.value.user.Email }}<span v-if="!resource.data.value.user.EmailVerifiedAt" class="b-sub">还没验证</span>
            </dd>
            <dt>注册</dt>
            <dd>{{ date(resource.data.value.user.CreatedAt) }}</dd>
            <dt v-if="resource.data.value.user.IsSuperuser">身份</dt>
            <dd v-if="resource.data.value.user.IsSuperuser">超级管理员</dd>
          </dl>
          <a class="c-btn c-btn--secondary c-btn--sm" :href="`/members/${resource.data.value.user.ID}/`" target="_blank" rel="noopener">成员页 →</a>
        </section>
        <section class="b-section">
          <h2 class="b-section__title">游戏和战队</h2>
          <dl class="b-kv">
            <dt>游戏 ID</dt>
            <dd>
              <template v-for="account in resource.data.value.game_accounts" :key="account.id">{{ account.battletag }}（{{ [account.tank_label, account.damage_label, account.support_label].filter(Boolean).join('、') }}）<br />
            </template>
            <template v-if="!resource.data.value.game_accounts.length">—</template>
          </dd>
          <dt>战队</dt>
          <dd><template v-for="(team, index) in resource.data.value.teams" :key="team.id">{{ team.name }}（{{ team.role === 'captain' ? '队长' : '成员' }}）<br v-if="index < resource.data.value.teams.length - 1" /></template><template v-if="!resource.data.value.teams.length">—</template></dd>
          <dt>联系方式</dt>
          <dd>
            <template v-for="contact in resource.data.value.contacts" :key="contact.id">{{ contact.type_label }} {{ contact.value }}<br />
          </template>
          <template v-if="!resource.data.value.contacts.length">—</template>
        </dd>
      </dl>
    </section>
  </aside>
  </div>
  </AdminPage>
</template>
