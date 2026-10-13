<script setup lang="ts">
import { computed, ref } from "vue"
import { postApiAdminUsersIdActivate, postApiAdminUsersIdDeactivate } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminSession } from "../../core/session"
import { useAdminAction } from "../../core/use-action"
import type { AdminUserDetailOut } from "../../pages/management/pending"
import ConfirmAction from "./ConfirmAction.vue"
import ActionState from "./ActionState.vue"
const props = defineProps<{ data: AdminUserDetailOut }>()
const emit = defineEmits<{ changed: [] }>()
const api = useAdminApi()
const session = useAdminSession()
const person = props.data.user
if (!person) throw new Error("UserAccountState requires a user")
const id = String(person.ID)
const own = computed(() => props.data.own_account === true || session.user.value?.id === person.ID)
const deleted = computed(() => props.data.is_deleted !== false)
const reason = ref("")
const active = useAdminAction<{ active: boolean; reason: string }, { result: string; message: string }>(
  (body, extras) => body.active ? postApiAdminUsersIdActivate(api, id, extras) : postApiAdminUsersIdDeactivate(api, id, { reason: body.reason }, extras), () => emit("changed"))
</script>
<template>
      <section v-if="!own" class="b-section">
        <h2 class="b-section__title">账号状态</h2>
        <form v-if="person.IsActive" class="b-form" @submit.prevent>
          <div class="c-field">
          <label class="c-field__label" for="stop-reason">停用原因<span class="c-field__req" aria-hidden="true">*</span></label>
          <input type="text" name="deactivation_note" required id="stop-reason" v-model="reason" class="c-input" maxlength="200" />
          <p class="c-field__help">只有管理员能看到（设计 3.7）。</p></div><div class="b-actions"><ConfirmAction title="停用账号" message="停用这个账号？不能再登录，待审批的入队申请会取消，当队长的战队会暂停招募。" label="停用账号" danger :pending="!active.canStart.value" @confirm="active.submit({ active: false, reason })" /></div>
        </form>
        <p v-else-if="deleted" class="b-section__text">{{ data.is_deleted === true ? '账号已注销：数据已匿名化，不能再启用。' : '账号停用状态尚未确认，请重新加载资料。' }}</p>
        <template v-else>
          <p class="b-section__text">账号已停用，不能登录。</p>
          <button class="c-btn c-btn--secondary c-btn--sm" :disabled="!active.canStart.value" @click="active.submit({ active: true, reason: '' })">重新启用</button>
        </template>
        <ActionState :message="active.message.value" :pending="active.pending.value" :uncertain="active.uncertain.value" @retry="active.retry" />
      </section>
</template>
