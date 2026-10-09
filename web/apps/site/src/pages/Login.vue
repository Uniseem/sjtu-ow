<script lang="ts">
import type { LoadCtx } from "../router"

export function load(_ctx?: LoadCtx) {
  return { title: "登录" }
}
</script>
<script setup lang="ts">
import { ref } from "vue"
import { useHead } from "@unhead/vue"
import { useRouter } from "vue-router"

useHead({ title: "登录 - SJTU-OW" })
const router = useRouter()

const email = ref("")
const password = ref("")
const submitting = ref(false)
const errorMsg = ref("")

async function onSubmit(e: Event) {
  e.preventDefault()
  submitting.value = true
  errorMsg.value = ""

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email: email.value, password: password.value }),
    })
    if (res.ok) {
      if (typeof window !== "undefined") {
        window.location.href = "/"
      } else {
        router.push("/")
      }
    } else {
      const err = await res.json().catch(() => ({}))
      errorMsg.value = err.message ?? "邮箱或密码错误"
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
      <h1 class="text-2xl font-bold mb-6 text-center">登录社区账号</h1>

      <div v-if="errorMsg" class="c-notice c-notice--err p-4 rounded bg-rose-950/60 border border-rose-800 text-rose-200 mb-6">
        <p>{{ errorMsg }}</p>
      </div>

      <form action="/accounts/login/" method="post" class="c-form space-y-4" @submit="onSubmit">
        <div class="c-field">
          <label class="c-field__label block mb-1">邮箱</label>
          <input v-model="email" type="email" name="email" required class="w-full p-2.5 rounded bg-stone-900 border border-stone-700" placeholder="your@email.com" />
        </div>

        <div class="c-field">
          <label class="c-field__label block mb-1">密码</label>
          <input v-model="password" type="password" name="password" required class="w-full p-2.5 rounded bg-stone-900 border border-stone-700" />
        </div>

        <div class="pt-4">
          <button type="submit" :disabled="submitting" class="c-btn c-btn--primary w-full">
            {{ submitting ? '登录中...' : '登录' }}
          </button>
        </div>

        <p class="text-center text-sm text-stone-400 mt-4">
          还没有账号？<a href="/accounts/signup/" class="text-primary-text underline">立即注册</a>
        </p>
      </form>
    </div>
  </main>
</template>
