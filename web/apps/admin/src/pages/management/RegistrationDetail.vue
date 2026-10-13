<script setup lang="ts">
import { ref } from "vue"
import { useRoute } from "vue-router"
import { postApiAdminRegistrationsIdApprove, postApiAdminRegistrationsIdReject } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import { useResource } from "./use-resource"
import { getRegistration } from "./pending"
import { date, state } from "./format"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ActionState from "../../components/management/ActionState.vue"
const api = useAdminApi()
const route = useRoute()
const confirm=useConfirm()
const note = ref("")
const resource = useResource(() => route.params.id, signal => getRegistration(api, String(route.params.id), { signal }))
const action = useAdminAction<{ kind: 'approve' | 'reject'; note: string }, unknown>((body, extras) => body.kind === 'approve' ? postApiAdminRegistrationsIdApprove(api,String(route.params.id),extras) : postApiAdminRegistrationsIdReject(api,String(route.params.id),{ note:body.note },extras),()=>resource.refresh())
function act(kind:'approve'|'reject'){if(action.canStart.value && confirm(kind==='approve'?'通过这份报名？':resource.data.value?.registration.can_revoke?'撤销这份报名的通过状态？':'驳回这份报名？'))void action.submit({kind,note:note.value})}
const actorLabels:Record<string,string>={captain:'队长',admin:'本站管理员',system:'系统',member:'队员'}
</script>
<template>
  <AdminPage :title="resource.data.value ? `${resource.data.value.registration.team_name} · ${resource.data.value.registration.tournament_title}` : '报名详情'" section="审核" back-href="/admin/registrations/">
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <div v-if="resource.data.value" class="b-split">
      <div class="b-form">
        <section class="b-form"><h2 class="b-section__title">名单快照</h2>
          <table class="c-table c-table--stack"><thead><tr><th>昵称</th><th>游戏 ID</th><th>坦克</th><th>输出</th><th>支援</th><th>交大</th><th>队长</th><th v-if="resource.data.value.show_contacts">联系方式</th></tr></thead>
            <tbody><tr v-for="person in resource.data.value.roster" :key="person.id"><td>{{ person.nickname }}{{ !person.account_active ? '（账号已停用）' : '' }}</td><td data-label="游戏 ID"><span class="b-mono">{{ person.battletag }}</span></td><td data-label="坦克">{{ person.tank_label }}</td><td data-label="输出">{{ person.damage_label }}</td><td data-label="支援">{{ person.support_label }}</td><td data-label="交大">{{ person.is_sjtu?'是':'否' }}</td><td data-label="队长">{{ person.is_captain?'是':'否' }}</td><td v-if="resource.data.value.show_contacts" data-label="联系方式">{{ person.contacts?.join('；') || '—' }}</td></tr></tbody>
          </table>
        </section>
        <section class="b-section"><h2 class="b-section__title">名单与战队当前成员的差异</h2><p v-if="!resource.data.value.registration.team_id" class="b-section__text">临时队伍没有战队，名单以编排页为准。</p><ul v-else-if="(resource.data.value.added?.length ?? 0) || (resource.data.value.removed?.length ?? 0)" class="b-list"><li v-for="name in resource.data.value.added" :key="'add:'+name">战队新增了 {{ name }}（不在名单里）</li><li v-for="name in resource.data.value.removed" :key="'remove:'+name">{{ name }} 已经不在战队里（仍在名单中）</li></ul><p v-else class="b-section__text">名单和当前成员一致。</p></section>
        <section class="b-form"><h2 class="b-section__title">状态日志</h2><table class="c-table c-table--stack"><thead><tr><th>时间</th><th>动作</th><th>变化</th><th>操作方</th><th class="is-num">版本</th><th>备注</th></tr></thead><tbody><tr v-for="record in resource.data.value.logs" :key="record.id"><td>{{ date(record.created_at) }}</td><td data-label="动作">{{ record.action }}</td><td data-label="变化">{{ record.from_status ? state(record.from_status) : '—' }} → {{ state(record.to_status) }}</td><td data-label="操作方">{{ actorLabels[record.actor_type] || record.actor_type }}</td><td class="is-num" data-label="版本">{{ record.roster_version }}</td><td data-label="备注">{{ record.note || '—' }}</td></tr></tbody></table></section>
      </div>
      <aside class="b-aside"><section class="b-section"><dl class="b-kv"><dt>赛事</dt><dd>{{ resource.data.value.registration.tournament_title }}{{ resource.data.value.registration.auto_approve?'（报名自动通过）':'' }}</dd><dt>{{ resource.data.value.registration.team_id?'战队':'临时队伍' }}</dt><dd>{{ resource.data.value.registration.team_name }}<template v-if="!resource.data.value.registration.team_id">（<RouterLink class="c-link" :to="`/admin/tournaments/${resource.data.value.registration.tournament_id}/teams/`">在队伍编排页管理</RouterLink>）</template></dd><dt>状态</dt><dd>{{ state(resource.data.value.registration.status) }}</dd><dt>名单版本</dt><dd>{{ resource.data.value.registration.roster_version }}</dd><dt>提交时间</dt><dd>{{ date(resource.data.value.registration.submitted_at) }}</dd><template v-if="resource.data.value.registration.status_note"><dt>最近备注</dt><dd>{{ resource.data.value.registration.status_note }}</dd></template></dl></section>
        <section class="b-section"><h2 class="b-section__title">处理</h2><form v-if="resource.data.value.registration.team_id && (resource.data.value.registration.can_approve || resource.data.value.registration.can_reject)" class="b-form" @submit.prevent><div class="c-field"><label class="c-field__label" for="note">备注</label><input id="note" v-model="note" name="note" class="c-input" maxlength="300" /><div class="c-field__help">驳回和撤销通过必填，会显示给队长。</div></div><div class="b-actions"><button v-if="resource.data.value.registration.can_approve" type="button" name="action" value="approve" class="c-btn c-btn--primary" :disabled="!action.canStart.value" @click="act('approve')">通过</button><button v-if="resource.data.value.registration.can_reject" type="button" name="action" :value="resource.data.value.registration.can_revoke ? 'revoke' : 'reject'" class="c-btn c-btn--danger" :disabled="!action.canStart.value || !note.trim()" @click="act('reject')">{{ resource.data.value.registration.can_revoke?'撤销通过':'驳回' }}</button></div></form><p v-else class="b-section__text">当前状态下没有可用的审核操作。</p><ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" /></section>
      </aside>
    </div>
  </AdminPage>
</template>
