<script setup lang="ts">
import { reactive, ref } from "vue"
import { postApiMeGameAccounts } from "@sjtu-ow/api"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import GameAccountFields from "./GameAccountFields.vue"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import type { GameAccount, GameValues } from "../pending-api"

const emit = defineEmits<{ created: [account: GameAccount] }>()
const api = useApi()
const battletag = ref("")
// Unranked is null. Bronze 5 is zero; neither is replaced with a default.
const values = reactive<GameValues>({ rank_tank: null, rank_damage: null, rank_support: null })
const mutation = useMutation(
  (body: GameValues & { battletag: string }, extras) => postApiMeGameAccounts(api, body, extras),
  (account) => {
    emit("created", account)
    battletag.value = ""
    values.rank_tank = null
    values.rank_damage = null
    values.rank_support = null
  },
)

function create(): void {
  void mutation.submit({ battletag: battletag.value.trim(), ...values })
}
</script>

<template>
  <form
    method="post"
    action="/me/game-accounts/"
    class="c-form"
    :aria-busy="mutation.pending.value || undefined"
    @submit.prevent="create"
  >
    <CMutationError
      :message="Object.keys(mutation.fields.value).length ? '' : mutation.message.value"
      :uncertain="mutation.uncertain.value"
      :pending="mutation.pending.value"
      @retry="mutation.retry"
    />
    <GameAccountFields
      :battletag="battletag"
      :values="values"
      :fields="mutation.fields.value"
      :disabled="mutation.pending.value || mutation.uncertain.value"
      @battletag="battletag = $event"
      @rank="(name, value) => values[name] = value"
    />
    <div class="flex flex-wrap gap-3">
      <button type="submit" class="c-btn c-btn--primary" :disabled="!mutation.canStart.value">添加</button>
      <a href="/me/game-accounts/" class="c-btn c-btn--quiet">取消</a>
    </div>
  </form>
</template>
