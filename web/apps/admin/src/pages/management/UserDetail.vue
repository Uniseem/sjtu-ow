<script setup lang="ts">
import { useRoute } from "vue-router"
import { getAdminUser, type AdminUserDetailOut } from "./pending"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import UserEditor from "../../components/management/UserEditor.vue"
import UserAccountState from "../../components/management/UserAccountState.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import UserRules from "../../components/management/UserRules.vue"
import { useResource } from "./use-resource"
import { useAdminApi } from "../../core/api"
import { date } from "./format"
const api = useAdminApi()
const route = useRoute()
const resource = useResource(() => route.params.id, signal => getAdminUser(api, String(route.params.id), { signal }))
function ranks(account: AdminUserDetailOut['game_accounts'][number]) {
  return [account.rank_tank != null && `坦克 ${account.tank_label}`, account.rank_damage != null && `输出 ${account.damage_label}`, account.rank_support != null && `支援 ${account.support_label}`].filter(Boolean).join('、') || '未定级'
}
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
            <dt>最后登录</dt><dd>{{ date(resource.data.value.last_login_at) }}</dd>
            <dt v-if="resource.data.value.user.IsSuperuser">身份</dt>
            <dd v-if="resource.data.value.user.IsSuperuser">超级管理员</dd>
            <template v-if="resource.data.value.user.DeactivationNote && !resource.data.value.user.IsActive"><dt>停用原因</dt><dd>{{ resource.data.value.user.DeactivationNote }}</dd></template>
          </dl>
          <a class="c-btn c-btn--secondary c-btn--sm" :href="`/members/${resource.data.value.user.ID}/`" target="_blank" rel="noopener">成员页<CIcon name="external" class="size-4" /></a>
        </section>
        <UserAccountState :key="`${resource.data.value.user.ID}:${resource.data.value.user.IsActive}`" :data="resource.data.value" @changed="resource.refresh" />
        <section class="b-section">
          <h2 class="b-section__title">游戏和战队</h2>
          <dl class="b-kv">
            <dt>游戏 ID</dt>
            <dd>
              <template v-for="(account, index) in resource.data.value.game_accounts" :key="account.id">{{ account.battletag }}（{{ ranks(account) }}）<br v-if="index < resource.data.value.game_accounts.length - 1" />
            </template>
            <template v-if="!resource.data.value.game_accounts.length">—</template>
          </dd>
          <dt>战队</dt>
          <dd><template v-for="(team, index) in resource.data.value.teams" :key="team.id">{{ team.name }}（{{ team.role === 'captain' ? '队长' : '队员' }}）<br v-if="index < resource.data.value.teams.length - 1" /></template><template v-if="!resource.data.value.teams.length">—</template></dd>
          <dt>联系方式</dt>
          <dd>
            <template v-for="(contact, index) in resource.data.value.contacts" :key="contact.id">{{ contact.type_label }} {{ contact.value }}<br v-if="index < resource.data.value.contacts.length - 1" />
          </template>
          <template v-if="!resource.data.value.contacts.length">—</template>
        </dd>
      </dl>
    </section>
  </aside>
  </div>
  </AdminPage>
</template>
