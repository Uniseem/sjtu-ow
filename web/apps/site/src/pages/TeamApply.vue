<script lang="ts">
import type { LoadCtx } from "../router"

export async function load(ctx?: LoadCtx) {
  const f = ctx?.fetch ?? fetch
  const base = ctx?.apiBase ?? ""
  const id = ctx?.params?.id ?? ""
  let team: any = null
  try {
    const res = await f(`${base}/api/teams/${id}`)
    if (res.ok) {
      team = await res.json()
    }
  } catch {}

  return {
    title: team?.name ? `申请加入 ${team.name}` : "申请加入战队",
    team,
  }
}
</script>
<script setup lang="ts">
import { inject, computed, ref } from "vue"
import { useHead } from "@unhead/vue"

const data = inject<any>("page-data")
const team = computed(() => data?.team)
useHead({ title: data?.title ? `${data.title} - SJTU-OW` : "申请加入战队 - SJTU-OW" })

const roleTank = ref(true)
const roleDamage = ref(true)
const roleSupport = ref(true)
const message = ref("")
const submitting = ref(false)
const applied = ref(false)
const letterBatch = ref<string | null>(null)
const errorMsg = ref("")

async function onSubmit(e: Event) {
  e.preventDefault()
  if (!team.value) return
  submitting.value = true
  errorMsg.value = ""

  try {
    const res = await fetch(`/api/teams/${team.value.id}/applications`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        role_tank: roleTank.value,
        role_damage: roleDamage.value,
        role_support: roleSupport.value,
        message: message.value,
      }),
    })
    if (res.ok) {
      applied.value = true
      const data = await res.json().catch(() => ({}))
      letterBatch.value = data.batch ?? "1"
    } else {
      const err = await res.json().catch(() => ({}))
      errorMsg.value = err.message ?? "申请提交失败"
    }
  } catch (err: any) {
    errorMsg.value = err.message ?? "网络请求失败"
  } finally {
    submitting.value = false
  }
}
</script>
<template>
  <main id="main" class="flex-1">
    <div v-if="team" class="l-container l-container--narrow py-12">
      <nav class="c-crumbs mb-6" aria-label="位置">
        <a href="/">首页</a><span class="c-crumbs__sep">/</span>
        <a href="/teams/">战队</a><span class="c-crumbs__sep">/</span>
        <a :href="`/teams/${team.id}/`">{{ team.name }}</a><span class="c-crumbs__sep">/</span>
        <span>申请入队</span>
      </nav>

      <h1 class="text-2xl font-bold mb-4">申请加入「{{ team.name }}」</h1>
      <p class="text-stone-300 mb-8">队长会看到你的昵称、意向位置和游戏 ID，审核通过后你就是队员了。</p>

      <div v-if="applied" class="space-y-6">
        <div class="c-notice c-notice--ok p-4 rounded bg-emerald-950/60 border border-emerald-800 text-emerald-200">
          <p class="font-bold text-lg">申请已提交</p>
          <p class="text-sm mt-1">你的入队申请已送达队长。</p>
        </div>

        <div v-if="letterBatch" class="p-6 rounded bg-stone-900 border border-stone-800">
          <h2 class="font-bold mb-2">通知队长</h2>
          <p class="text-stone-400 text-sm mb-4">是否要向队长发送邮件通知提醒审核？</p>
          <form :action="`/teams/${team.id}/`" method="get" data-held-letters="1">
            <span data-held-letter="1" hidden></span>
            <a :href="`/teams/${team.id}/`" class="c-btn c-btn--primary">发信并回到战队</a>
          </form>
        </div>
      </div>

      <div v-else>
        <div v-if="errorMsg" class="c-notice c-notice--err p-4 rounded bg-rose-950/60 border border-rose-800 text-rose-200 mb-6">
          <p>{{ errorMsg }}</p>
        </div>

        <form method="post" class="c-form max-w-xl space-y-6" @submit="onSubmit">
          <fieldset class="c-field">
            <legend class="c-field__label mb-3 font-semibold">意向位置（至少选一个）</legend>
            <div class="c-choices flex gap-4">
              <label class="c-choice flex items-center gap-2">
                <input v-model="roleTank" type="checkbox" name="role_tank" />
                <span>重装</span>
              </label>
              <label class="c-choice flex items-center gap-2">
                <input v-model="roleDamage" type="checkbox" name="role_damage" />
                <span>输出</span>
              </label>
              <label class="c-choice flex items-center gap-2">
                <input v-model="roleSupport" type="checkbox" name="role_support" />
                <span>支援</span>
              </label>
            </div>
          </fieldset>

          <div class="c-field">
            <label class="c-field__label font-semibold">入队留言（选填）</label>
            <textarea
              v-model="message"
              name="message"
              rows="3"
              class="w-full mt-2 p-3 bg-stone-900 border border-stone-700 rounded text-stone-100"
              placeholder="向队长介绍一下自己吧"
            ></textarea>
          </div>

          <div class="pt-4 flex gap-4">
            <button type="submit" :disabled="submitting" class="c-btn c-btn--primary">
              {{ submitting ? '提交中...' : '提交申请' }}
            </button>
            <a :href="`/teams/${team.id}/`" class="c-btn c-btn--quiet">取消</a>
          </div>
        </form>
      </div>
    </div>
    <div v-else class="l-container py-20 text-center text-stone-400">
      <p class="text-xl">战队不存在</p>
      <a href="/teams/" class="c-btn c-btn--quiet mt-4">返回战队列表</a>
    </div>
  </main>
</template>
