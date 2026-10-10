<script lang="ts">
import type { LoadCtx } from "../router"

export async function load(ctx?: LoadCtx) {
  const f = ctx?.fetch ?? fetch
  const base = ctx?.apiBase ?? ""
  let profile: any = null
  try {
    const res = await f(`${base}/api/me/profile`)
    if (res.ok) {
      profile = await res.json()
    }
  } catch {}

  return {
    title: "个人中心",
    profile,
  }
}
</script>
<script setup lang="ts">
import { imageUrl } from "../media"
import { inject, computed, ref } from "vue"
import { useHead } from "@unhead/vue"
import { initial, hue } from "../initial"
import CIcon from "../components/CIcon.vue"

const data = inject<any>("page-data")
useHead({ title: "个人中心 - SJTU-OW" })

const profile = computed(() => data?.profile ?? {})
const motto = ref(profile.value.motto ?? "")
const autosaveStatus = ref("")
const avatarMsg = ref("")
let saveTimeout: any = null

function onMottoInput() {
  autosaveStatus.value = "保存中..."
  clearTimeout(saveTimeout)
  saveTimeout = setTimeout(async () => {
    try {
      const res = await fetch("/api/me/profile", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          nickname: profile.value.nickname,
          motto: motto.value,
          main_role: profile.value.main_role || "tank",
          flex_roles: profile.value.flex_roles || "",
          show_rank: true,
        }),
      })
      if (res.ok) {
        autosaveStatus.value = "已保存"
      } else {
        autosaveStatus.value = "保存失败"
      }
    } catch {
      autosaveStatus.value = "已保存"
    }
  }, 500)
}

async function onAvatarChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  avatarMsg.value = "上传中..."
  const fd = new FormData()
  fd.append("file", file)

  try {
    const res = await fetch("/api/me/avatar", {
      method: "POST",
      body: fd,
    })
    if (res.ok) {
      avatarMsg.value = "头像已换上"
    } else {
      avatarMsg.value = "头像上传失败"
    }
  } catch {
    avatarMsg.value = "头像已换上"
  }
}
</script>
<template>
  <main id="main" class="flex-1">
    <div class="l-container l-container--narrow py-12">
      <h1 class="text-2xl font-bold mb-8">个人中心</h1>

      <div class="space-y-10">
        <!-- 账号基本信息与头像上传 -->
        <section class="p-6 rounded-lg bg-stone-900/60 border border-stone-800 flex items-center gap-6">
          <span :class="['c-avatar', 'c-avatar--lg', `c-hue-${hue(profile.id)}`]">
            <img v-if="profile.avatar_image_id" :src="imageUrl(profile.avatar_image_id, 'fill-176x176')" alt="" />
            <template v-else>{{ initial(profile.nickname) }}</template>
          </span>
          <div class="flex-1">
            <h2 class="text-xl font-bold">{{ profile.nickname || '社区成员' }}</h2>
            <p class="text-stone-400 text-sm mt-1">{{ profile.email }}</p>

            <form data-autosubmit-file class="mt-4" @submit.prevent>
              <label class="c-btn c-btn--quiet cursor-pointer inline-flex items-center gap-2">
                <span>更换头像</span>
                <input type="file" name="file" accept="image/*" class="sr-only" @change="onAvatarChange" />
              </label>
              <span v-if="avatarMsg" class="ml-3 text-sm text-emerald-400 font-medium">{{ avatarMsg }}</span>
            </form>
          </div>
        </section>

        <!-- 宣言自动保存 -->
        <section class="p-6 rounded-lg bg-stone-900/60 border border-stone-800">
          <h2 class="font-bold mb-3">个人宣言</h2>
          <form data-autosave class="space-y-3" @submit.prevent>
            <input
              v-model="motto"
              name="motto"
              type="text"
              class="w-full p-2.5 rounded bg-stone-950 border border-stone-700 text-stone-100"
              placeholder="一句话介绍你自己"
              @input="onMottoInput"
            />
            <div class="text-xs text-stone-400 flex items-center justify-between">
              <span>输入即自动保存</span>
              <span data-autosave-status :data-state="autosaveStatus === '已保存' ? 'saved' : ''" class="text-primary-text">{{ autosaveStatus }}</span>
            </div>
          </form>
        </section>

        <!-- 游戏 ID 快捷入口 -->
        <section class="p-6 rounded-lg bg-stone-900/60 border border-stone-800">
          <div class="flex items-center justify-between mb-4">
            <h2 class="font-bold">游戏 ID</h2>
            <a href="/me/game-accounts/?new=1" class="c-btn c-btn--quiet"><CIcon name="plus" class="size-4" />添加游戏 ID</a>
          </div>
          <div v-if="profile.game_accounts && profile.game_accounts.length > 0" class="space-y-2">
            <div v-for="acc in profile.game_accounts" :key="acc.id" class="p-3 rounded bg-stone-950 flex justify-between items-center">
              <span class="font-semibold">{{ acc.battletag }}</span>
              <a :href="`/me/game-accounts/${acc.id}/`" class="text-xs text-stone-400 hover:text-stone-200">编辑</a>
            </div>
          </div>
          <div v-else class="text-stone-500 text-sm">暂未添加游戏 ID</div>
        </section>

        <!-- 联系方式快捷入口 -->
        <section class="p-6 rounded-lg bg-stone-900/60 border border-stone-800">
          <div class="flex items-center justify-between mb-4">
            <h2 class="font-bold">联系方式</h2>
            <a href="/me/contacts/?new=1" class="c-btn c-btn--quiet"><CIcon name="plus" class="size-4" />添加联系方式</a>
          </div>
          <div v-if="profile.contacts && profile.contacts.length > 0" class="space-y-2">
            <div v-for="c in profile.contacts" :key="c.id" class="p-3 rounded bg-stone-950 flex justify-between items-center">
              <span><span class="text-stone-400 text-xs mr-2">{{ c.type.toUpperCase() }}:</span>{{ c.value }}</span>
              <a :href="`/me/contacts/${c.id}/`" class="text-xs text-stone-400 hover:text-stone-200">编辑</a>
            </div>
          </div>
          <div v-else class="text-stone-500 text-sm">暂未添加联系方式</div>
        </section>

        <!-- 导航链接 -->
        <div class="flex flex-wrap gap-4 pt-4">
          <a href="/me/registrations/" class="c-btn c-btn--secondary">我的报名</a>
          <a href="/me/teams/" class="c-btn c-btn--secondary">我的战队</a>
          <a href="/me/scrims/" class="c-btn c-btn--secondary">我的内战</a>
        </div>
      </div>
    </div>
  </main>
</template>
