<script lang="ts">
import type { LoadCtx } from "../router"

export async function load(ctx?: LoadCtx) {
  const f = ctx?.fetch ?? fetch
  const base = ctx?.apiBase ?? ""
  const id = ctx?.params?.id ?? ""
  let scrim: any = null
  let accounts: any[] = []
  try {
    const [scrimRes, profRes] = await Promise.all([
      f(`${base}/api/scrims/${id}`),
      f(`${base}/api/me/profile`),
    ])
    if (scrimRes.ok) {
      scrim = await scrimRes.json()
    }
    if (profRes.ok) {
      const pData = await profRes.json()
      accounts = pData.game_accounts ?? []
    }
  } catch {}

  return {
    title: scrim?.title ?? "内战详情",
    scrim,
    accounts,
  }
}
</script>
<script setup lang="ts">
import { inject, computed, ref } from "vue"
import { useHead } from "@unhead/vue"
import CSeats from "../components/CSeats.vue"
import CIcon from "../components/CIcon.vue"
import { VIEWER, type Viewer } from "../viewer"

const data = inject<any>("page-data")
const viewer = inject<Viewer>(VIEWER)
const scrim = computed(() => data?.scrim)
const accounts = computed(() => data?.accounts ?? [])
useHead({ title: scrim.value?.title ? `${scrim.value.title} - SJTU-OW` : "内战详情 - SJTU-OW" })

const selectedAccount = ref(accounts.value[0]?.id ?? "")
const selectedRoles = ref<string[]>(["tank", "damage", "support"])
const submitting = ref(false)
const successMsg = ref("")
const errorMsg = ref("")

async function onSubmit(e: Event) {
  e.preventDefault()
  if (!scrim.value) return
  submitting.value = true
  errorMsg.value = ""
  successMsg.value = ""

  try {
    const res = await fetch(`/api/scrims/${scrim.value.id}/signup`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        game_account_id: Number(selectedAccount.value),
        roles: selectedRoles.value,
      }),
    })
    if (res.ok) {
      successMsg.value = "报名成功"
    } else {
      const err = await res.json().catch(() => ({}))
      errorMsg.value = err.message ?? "报名失败，请重试"
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
    <div v-if="scrim">
      <header class="c-stage">
        <div class="l-container l-container--narrow c-stage__body">
          <nav class="c-crumbs" aria-label="位置">
            <a href="/">首页</a><span class="c-crumbs__sep">/</span>
            <a href="/scrims/">内战</a><span class="c-crumbs__sep">/</span>
            <span>{{ scrim.title }}</span>
          </nav>
          <p class="c-stage__tags">
            <span v-if="scrim.status === 'open'" class="c-status c-status--live">报名中</span>
            <span v-else-if="scrim.status === 'finished'" class="c-status">已结束</span>
            <span v-else class="c-status">报名已截止</span>
            <span class="c-tag">{{ scrim.format === 'rq_6v6' ? '6v6 职责预设' : '5v5 职责预设' }}</span>
          </p>
          <h1 class="c-stage__title">{{ scrim.title }}</h1>
          <dl class="c-stage__facts">
            <div><dt>开始时间</dt><dd><time>{{ scrim.starts_at }}</time></dd></div>
            <div><dt>已报名</dt><dd>{{ scrim.signups?.length ?? 0 }} / {{ scrim.capacity ?? 10 }} 人</dd></div>
          </dl>
          <CSeats :taken="scrim.signups?.length ?? 0" :total="scrim.capacity ?? 10" extra="c-stage__meter" />
        </div>
      </header>

      <div class="l-container l-container--narrow l-section">
        <div class="l-split">
          <div class="flex min-w-0 flex-col gap-12">
            <!-- 报名区域 -->
            <section class="c-panel" aria-label="报名">
              <div v-if="successMsg" class="c-notice c-notice--ok p-4 rounded bg-emerald-950/60 border border-emerald-800 text-emerald-200">
                <p class="font-bold text-lg">报名成功</p>
                <p class="text-sm mt-1">你已成功报名本场内战，管理员稍后将安排分队。</p>
              </div>

              <div v-else-if="errorMsg" class="c-notice c-notice--err p-4 rounded bg-rose-950/60 border border-rose-800 text-rose-200 mb-4">
                <p>{{ errorMsg }}</p>
              </div>

              <form
                v-if="!successMsg"
                :action="`/scrims/${scrim.id}/signup/`"
                method="post"
                class="c-form"
                @submit="onSubmit"
              >
                <div class="c-field">
                  <label class="c-field__label">游戏 ID<span class="c-field__req" aria-hidden="true">*</span></label>
                  <select v-if="accounts.length > 0" v-model="selectedAccount" name="game_account" required class="w-full">
                    <option v-for="acc in accounts" :key="acc.id" :value="acc.id">{{ acc.battletag }}</option>
                  </select>
                  <div v-else class="text-sm text-stone-400">
                    你还没有添加游戏 ID，请先在<a href="/me/game-accounts/?new=1" class="text-primary-text underline ml-1">个人中心</a>添加。
                  </div>
                </div>

                <fieldset class="c-field mt-4">
                  <legend class="c-field__label mb-2">能打的位置（至少一个）</legend>
                  <div class="c-choices flex gap-4">
                    <label class="c-choice flex items-center gap-2">
                      <input v-model="selectedRoles" type="checkbox" name="roles" value="tank" />
                      <CIcon name="role-tank" class="size-4" />
                      <span>坦克</span>
                    </label>
                    <label class="c-choice flex items-center gap-2">
                      <input v-model="selectedRoles" type="checkbox" name="roles" value="damage" />
                      <CIcon name="role-damage" class="size-4" />
                      <span>输出</span>
                    </label>
                    <label class="c-choice flex items-center gap-2">
                      <input v-model="selectedRoles" type="checkbox" name="roles" value="support" />
                      <CIcon name="role-support" class="size-4" />
                      <span>支援</span>
                    </label>
                  </div>
                </fieldset>

                <div class="mt-6">
                  <button type="submit" :disabled="submitting || accounts.length === 0" class="c-btn c-btn--primary">
                    {{ submitting ? '提交中...' : '报名' }}
                  </button>
                </div>
              </form>
            </section>

            <!-- 报名列表 -->
            <section aria-labelledby="s-signups">
              <div class="c-sectionhead"><h2 id="s-signups">报名情况</h2></div>
              <p class="text-stone-400 mb-4">共 {{ scrim.signups?.length ?? 0 }} 人报名</p>
              <table v-if="scrim.signups && scrim.signups.length > 0" class="c-table">
                <thead>
                  <tr>
                    <th scope="col" class="w-12">序号</th>
                    <th scope="col">昵称</th>
                    <th scope="col">游戏 ID</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(s, idx) in scrim.signups" :key="s.id">
                    <td class="font-numeric">{{ idx + 1 }}</td>
                    <td>{{ s.user_nickname }}</td>
                    <td>{{ s.battletag }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-else class="text-stone-500 py-4">暂无人报名</div>
            </section>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="l-container py-20 text-center text-stone-400">
      <p class="text-xl">内战不存在</p>
      <a href="/scrims/" class="c-btn c-btn--quiet mt-4">返回内战列表</a>
    </div>
  </main>
</template>
