<script lang="ts">
import type { LoadCtx } from "../router"

export async function load(ctx?: LoadCtx) {
  const f = ctx?.fetch ?? fetch
  const base = ctx?.apiBase ?? ""
  let contacts: any[] = []
  try {
    const res = await f(`${base}/api/me/profile`)
    if (res.ok) {
      const data = await res.json()
      contacts = data.contacts ?? []
    }
  } catch {}

  return {
    title: "联系方式",
    contacts,
  }
}
</script>
<script setup lang="ts">
import { inject, computed, ref } from "vue"
import { useHead } from "@unhead/vue"

const data = inject<any>("page-data")
useHead({ title: "联系方式 - 个人中心 - SJTU-OW" })

const contacts = computed(() => data?.contacts ?? [])
const contactType = ref("qq")
const contactValue = ref("")
const addedValue = ref("")
const submitting = ref(false)

async function onSubmit(e: Event) {
  e.preventDefault()
  submitting.value = true
  try {
    const res = await fetch("/api/me/contacts", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        type: contactType.value,
        value: contactValue.value,
      }),
    })
    addedValue.value = contactValue.value
    if (res.ok) {
      const c = await res.json().catch(() => null)
      if (c) contacts.value.push(c)
    }
  } catch {
    addedValue.value = contactValue.value
  } finally {
    submitting.value = false
  }
}
</script>
<template>
  <main id="main" class="flex-1">
    <div class="l-container l-container--narrow py-12 max-w-xl mx-auto">
      <nav class="c-crumbs mb-6" aria-label="位置">
        <a href="/">首页</a><span class="c-crumbs__sep">/</span>
        <a href="/me/">个人中心</a><span class="c-crumbs__sep">/</span>
        <span>联系方式</span>
      </nav>

      <h1 class="text-2xl font-bold mb-6">添加联系方式</h1>

      <form action="/me/contacts/" method="post" class="c-form space-y-4" @submit="onSubmit">
        <div class="c-field">
          <label class="c-field__label block mb-1">类型<span class="text-rose-500">*</span></label>
          <select v-model="contactType" name="type" required class="w-full p-2.5 rounded bg-stone-900 border border-stone-700 text-stone-100">
            <option value="qq">QQ 号</option>
            <option value="wechat">微信</option>
            <option value="phone">手机号</option>
          </select>
        </div>

        <div class="c-field">
          <label class="c-field__label block mb-1">号码 / 账号<span class="text-rose-500">*</span></label>
          <input
            v-model="contactValue"
            type="text"
            name="value"
            required
            class="w-full p-2.5 rounded bg-stone-900 border border-stone-700 text-stone-100"
            placeholder="例如 123456789"
          />
        </div>

        <div class="pt-4">
          <button type="submit" :disabled="submitting || !contactValue" class="c-btn c-btn--primary">
            {{ submitting ? '保存中...' : '保存联系方式' }}
          </button>
        </div>
      </form>

      <div v-if="addedValue" class="mt-8 p-4 rounded bg-emerald-950/60 border border-emerald-800 text-emerald-200">
        已添加联系方式：<span class="font-bold">{{ addedValue }}</span>
      </div>

      <div v-if="contacts.length > 0" class="mt-10">
        <h2 class="font-bold text-lg mb-4">已有联系方式</h2>
        <ul class="space-y-2">
          <li v-for="c in contacts" :key="c.id" class="p-3 rounded bg-stone-900 border border-stone-800 flex justify-between">
            <span class="font-semibold">{{ c.type.toUpperCase() }}: {{ c.value }}</span>
          </li>
        </ul>
      </div>
    </div>
  </main>
</template>
