<script lang="ts">
import type { LoadCtx } from "../router"

export function load(_ctx?: LoadCtx) {
  return { title: "注册" }
}
</script>
<script setup lang="ts">
import { ref } from "vue"
import { useHead } from "@unhead/vue"
import { useRouter } from "vue-router"

useHead({ title: "注册 - SJTU-OW" })
const router = useRouter()

const email = ref("")
const nickname = ref("")
const password1Val = ref("")
const password2Val = ref("")
const isSjtu = ref("true")
const agreeTerms = ref(false)
const agreeCrossBorder = ref(false)
const submitting = ref(false)
const errorMsg = ref("")

async function onSubmit(e: Event) {
  e.preventDefault()
  if (password1Val.value !== password2Val.value) {
    errorMsg.value = "两次输入的密码不一致"
    return
  }
  submitting.value = true
  errorMsg.value = ""

  try {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        email: email.value,
        nickname: nickname.value,
        password: password1Val.value,
        confirm_password: password2Val.value,
        is_sjtu: isSjtu.value === "true",
        agree_terms: agreeTerms.value,
        agree_cross_border: agreeCrossBorder.value,
      }),
    })
    if (res.ok) {
      const target = `/accounts/confirm-email/?email=${encodeURIComponent(email.value)}`
      if (typeof window !== "undefined") {
        window.location.href = target
      } else {
        router.push(target)
      }
    } else {
      const err = await res.json().catch(() => ({}))
      errorMsg.value = err.message ?? "注册失败，请检查输入"
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
      <h1 class="text-2xl font-bold mb-6 text-center">加入 SJTU-OW 社区</h1>

      <div v-if="errorMsg" class="c-notice c-notice--err p-4 rounded bg-rose-950/60 border border-rose-800 text-rose-200 mb-6">
        <p>{{ errorMsg }}</p>
      </div>

      <form action="/accounts/signup/" method="post" class="c-form space-y-4" @submit="onSubmit">
        <div class="c-field">
          <label class="c-field__label block mb-1">邮箱地址<span class="text-rose-500">*</span></label>
          <input v-model="email" type="email" name="email" required class="w-full p-2.5 rounded bg-stone-900 border border-stone-700" placeholder="交大邮箱或常用邮箱" />
        </div>

        <div class="c-field">
          <label class="c-field__label block mb-1">社区昵称<span class="text-rose-500">*</span></label>
          <input v-model="nickname" type="text" name="nickname" required class="w-full p-2.5 rounded bg-stone-900 border border-stone-700" placeholder="将在社区各处显示" />
        </div>

        <div class="c-field">
          <label class="c-field__label block mb-1">设置密码<span class="text-rose-500">*</span></label>
          <input v-model="password1Val" type="password" name="password1" required class="w-full p-2.5 rounded bg-stone-900 border border-stone-700" />
        </div>

        <div class="c-field">
          <label class="c-field__label block mb-1">确认密码<span class="text-rose-500">*</span></label>
          <input v-model="password2Val" type="password" name="password2" required class="w-full p-2.5 rounded bg-stone-900 border border-stone-700" />
        </div>

        <fieldset class="c-field">
          <legend class="c-field__label mb-2">是否上海交通大学在读或校友</legend>
          <div class="flex gap-4">
            <label class="flex items-center gap-2">
              <input v-model="isSjtu" type="radio" name="is_sjtu" value="true" />
              <span>是</span>
            </label>
            <label class="flex items-center gap-2">
              <input v-model="isSjtu" type="radio" name="is_sjtu" value="false" />
              <span>否（校外玩家）</span>
            </label>
          </div>
        </fieldset>

        <div class="space-y-2 pt-2 text-sm text-stone-300">
          <label class="flex items-start gap-2">
            <input v-model="agreeTerms" type="checkbox" name="agree_terms" required class="mt-1" />
            <span>我已阅读并同意<a href="/terms/" target="_blank" class="text-primary-text underline">用户协议</a>与<a href="/privacy/" target="_blank" class="text-primary-text underline">隐私政策</a></span>
          </label>
          <label class="flex items-start gap-2">
            <input v-model="agreeCrossBorder" type="checkbox" name="agree_cross_border" required class="mt-1" />
            <span>我知晓本站涉及数据出境传输与安全合规要求</span>
          </label>
        </div>

        <div class="pt-4">
          <button type="submit" :disabled="submitting" class="c-btn c-btn--primary w-full">
            {{ submitting ? '注册中...' : '提交注册' }}
          </button>
        </div>

        <p class="text-center text-sm text-stone-400 mt-4">
          已有账号？<a href="/accounts/login/" class="text-primary-text underline">前往登录</a>
        </p>
      </form>
    </div>
  </main>
</template>
