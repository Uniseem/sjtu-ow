<script lang="ts">
import type { LoadCtx } from "../router"

export function load(_ctx?: LoadCtx) {
  return { title: "验证邮箱" }
}
</script>
<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useHead } from "@unhead/vue"
import { useRouter, useRoute } from "vue-router"

useHead({ title: "验证邮箱 - SJTU-OW" })
const router = useRouter()
const route = useRoute()

const email = ref("")
const code = ref("")
const submitting = ref(false)
const errorMsg = ref("")

onMounted(() => {
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search)
    email.value = params.get("email") || (route.query.email as string) || ""
  }
})

async function onSubmit(e: Event) {
  e.preventDefault()
  if (!email.value) {
    errorMsg.value = "请输入邮箱地址"
    return
  }
  submitting.value = true
  errorMsg.value = ""

  try {
    const res = await fetch("/api/auth/verify-email", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        email: email.value.trim(),
        code: code.value.trim().toUpperCase(),
      }),
    })
    if (res.ok) {
      if (typeof window !== "undefined") {
        window.location.href = "/me/"
      } else {
        router.push("/me/")
      }
    } else {
      const err = await res.json().catch(() => ({}))
      errorMsg.value = err.message ?? "验证码无效或已过期"
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
    <div class="l-container l-container--narrow py-12 max-w-md mx-auto">
      <h1 class="text-2xl font-bold mb-4 text-center">输入邮箱验证码</h1>
      <p class="text-stone-300 text-sm text-center mb-6">
        我们已向你的邮箱发送了 6 位验证码，请查收并填入下方。
      </p>

      <div v-if="errorMsg" class="c-notice c-notice--err p-4 rounded bg-rose-950/60 border border-rose-800 text-rose-200 mb-6">
        <p>{{ errorMsg }}</p>
      </div>

      <form action="/accounts/confirm-email/" method="post" class="c-form space-y-4" @submit="onSubmit">
        <div class="c-field" v-if="!email">
          <label class="c-field__label block mb-1 text-sm font-medium">邮箱地址</label>
          <input
            v-model="email"
            type="email"
            name="email"
            required
            class="w-full p-2.5 rounded bg-stone-900 border border-stone-700 text-stone-100"
            placeholder="name@example.com"
          />
        </div>
        <div v-else class="text-sm text-stone-400 text-center mb-2">
          正在为 <strong class="text-amber-400">{{ email }}</strong> 核验验证码
          <input type="hidden" name="email" :value="email" />
        </div>

        <div class="c-field">
          <label class="c-field__label block mb-1">6 位验证码</label>
          <input
            v-model="code"
            type="text"
            name="code"
            required
            maxlength="6"
            class="w-full p-3 rounded bg-stone-900 border border-stone-700 text-center text-2xl tracking-widest uppercase font-mono"
            placeholder="ABC123"
          />
        </div>

        <div class="pt-4">
          <button type="submit" :disabled="submitting || !code" class="c-btn c-btn--primary w-full">
            {{ submitting ? '验证中...' : '确认验证' }}
          </button>
        </div>
      </form>
    </div>
  </main>
</template>
