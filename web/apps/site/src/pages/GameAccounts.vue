<script lang="ts">
import type { LoadCtx } from "../router"
import { httpError } from "../router"
import { loadPersonal, personalId } from "../personal"

export async function load(ctx: LoadCtx) {
  const result = await loadPersonal(ctx, "游戏 ID 与段位")
  const editId = ctx.params.id ? personalId(ctx.params.id) : undefined
  if (editId && !result.profile.game_accounts.some((account) => account.id === editId)) throw httpError(404)
  return { ...result, newItem: ctx.query.new === "1" && !editId, editId }
}
</script>

<script setup lang="ts">
import { computed, inject, reactive, ref, watch } from "vue"
import { useHead } from "@unhead/vue"
import { useRouter } from "vue-router"
import { deleteApiMeGameAccountsId } from "@sjtu-ow/api"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import PersonalLayout from "../components/PersonalLayout.vue"
import GameAccountCard from "../components/GameAccountCard.vue"
import GameAccountEditor from "../components/GameAccountEditor.vue"
import GameAccountCreate from "../components/GameAccountCreate.vue"
import { requirePageData, usePersonalUser } from "../personal"
import type { PersonalPageData } from "../personal"
import type { GameAccount } from "../pending-api"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"

const data = requirePageData(inject<PersonalPageData>("page-data"))
const profile = reactive({ ...data.profile, game_accounts: [...data.profile.game_accounts] })
const user = usePersonalUser(profile)
const api = useApi()
const router = useRouter()
const confirm = useConfirm()
const notice = ref("")
const newItem = ref(data.newItem === true)
const editId = ref(data.editId)
const limit = computed(() => profile.max_game_accounts)
const atLimit = computed(() => limit.value !== undefined && profile.game_accounts.length >= limit.value)

const remove = useMutation(
  (id: number, extras) => deleteApiMeGameAccountsId(api, id, extras),
  () => {
    profile.game_accounts = profile.game_accounts.filter((account) => account.id !== deletingId.value)
    notice.value = "游戏 ID 已删除。"
  },
)
const deletingId = ref<number | null>(null)

function removeAccount(id: number): void {
  if (remove.pending.value || remove.uncertain.value) return
  if (!confirm("确定删除这个游戏 ID？")) return
  deletingId.value = id
  notice.value = ""
  void remove.submit(id)
}

function created(account: GameAccount): void {
  // Only the real POST response is added; never add the input optimistically.
  profile.game_accounts.push(account)
  newItem.value = false
  notice.value = "游戏 ID 已添加。"
  void router.replace("/me/game-accounts/")
}

async function finished(): Promise<void> {
  editId.value = undefined
  await router.replace("/me/game-accounts/")
}

watch(() => data.profile, (next) => {
  Object.assign(profile, next, { game_accounts: [...next.game_accounts] })
  newItem.value = data.newItem === true
  editId.value = data.editId
})
watch(() => [data.newItem, data.editId], () => {
  newItem.value = data.newItem === true
  editId.value = data.editId
})

useHead({ title: "游戏 ID 与段位 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })
</script>

<template>
  <PersonalLayout title="游戏 ID 与段位" current="/me/game-accounts/" :profile="profile" :user="user">
    <CMutationError
      :message="remove.message.value"
      :uncertain="remove.uncertain.value"
      :pending="remove.pending.value"
      @retry="remove.retry"
    />
    <p v-if="notice" class="text-sm text-fg-2" role="status">{{ notice }}</p>
    <div id="game-account-list" class="flex flex-col gap-4">
      <template v-for="account in profile.game_accounts" :key="account.id">
        <article v-if="editId === account.id" :id="'game-account-' + account.id" class="c-panel" data-game-account>
          <GameAccountEditor :key="account.id" :account="account" @done="finished" />
        </article>
        <GameAccountCard
          v-else
          :account="account"
          :pending="remove.pending.value || remove.uncertain.value"
          @remove="removeAccount"
        />
      </template>
      <CEmpty
        v-if="!profile.game_accounts.length"
        title="还没有游戏 ID"
        message="至少绑定 1 个游戏 ID 后才能报名赛事和内战。"
      />
      <div id="create-game-account">
        <GameAccountCreate v-if="newItem && !atLimit" @created="created" />
      </div>
      <p v-if="atLimit" class="text-sm text-fg-2">每人最多绑定 {{ limit }} 个游戏 ID。</p>
      <a v-else href="/me/game-accounts/?new=1" class="c-btn c-btn--primary self-start">
        <CIcon name="plus" />新增游戏 ID
      </a>
    </div>
  </PersonalLayout>
</template>
