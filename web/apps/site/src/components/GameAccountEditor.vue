<script setup lang="ts">
import CAutosave from "@sjtu-ow/ui/CAutosave.vue"
import GameAccountFields from "./GameAccountFields.vue"
import type { GameAccount } from "../pending-api"
import { patchPersonalGameAccount, validVersion } from "../pending-api"
import { gameValues, readGameEditCurrent } from "../personal"
import { useApi } from "../api"
import { useAutosave } from "../use-autosave"

const props = defineProps<{ account: GameAccount }>()
const emit = defineEmits<{ done: [] }>()
const api = useApi()
const save = useAutosave({
  initial: { ...gameValues(props.account), battletag: props.account.battletag },
  version: validVersion(props.account.version) ? props.account.version : 0,
  available: () => validVersion(props.account.version),
  readCurrent: readGameEditCurrent,
  transport: (body, key, signal) => patchPersonalGameAccount(api, props.account.id, body, { key, signal, unauthorized: "throw" }),
})

async function done(): Promise<void> {
  if (await save.save()) emit("done")
}
</script>

<template>
  <form
    method="post"
    :action="'/me/game-accounts/' + account.id + '/'"
    class="c-form"
    data-autosave
    :aria-busy="save.pending.value || undefined"
    @submit.prevent="done"
  >
    <CAutosave
      bare
      :idle-message="validVersion(account.version) ? '改了就自动保存' : ''"
      :state="save.snapshot.value.state"
      :message="save.snapshot.value.message"
      :dirty="save.dirty.value"
      :pending="save.pending.value"
      :login-required="save.snapshot.value.loginRequired"
      :login-href="'/accounts/login/?next=' + encodeURIComponent('/me/game-accounts/' + account.id + '/')"
      @retry="save.save"
    />
    <GameAccountFields
      :battletag="save.values.value.battletag"
      :values="save.values.value"
      :fields="save.fields.value"
      :disabled="!validVersion(account.version)"
      :prefix="'edit_' + account.id"
      editing
      @battletag="save.set('battletag', $event, 'text')"
      @rank="(name, value) => save.set(name, value, 'choice')"
      @blur="save.flush"
    />

    <p v-if="!validVersion(account.version)" class="text-sm text-fg-2" role="status">暂时无法保存，请稍后再试。</p>
    <div class="flex flex-wrap gap-3">
      <button type="submit" class="c-btn c-btn--primary" :disabled="save.pending.value">完成</button>
    </div>
  </form>
</template>
