<script setup lang="ts">
import { showReadError } from "../../core/read-error"
import { onMounted, shallowRef } from "vue"
import { useRoute } from "vue-router"
import { ApiError, getApiAdminScrimsIdBoard } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import AdminPage from "../../components/AdminPage.vue"
import AdminNotice from "../../components/AdminNotice.vue"
import { numericId } from "./domain"

const api = useAdminApi()
const route = useRoute()
const id = numericId(route.params.id)
const title = shallowRef("分队文字")
const text = shallowRef("")
const pending = shallowRef(true)
const error = shallowRef("")
const copied = shallowRef("")

async function load(): Promise<void> {
  pending.value = true
  error.value = ""
  try {
    if (!id) throw new ApiError(404, "not_found", "找不到这个页面")
    const result = await getApiAdminScrimsIdBoard(api, id)
    if (!result.scrim) throw new ApiError(404, "not_found", "找不到这个页面")
    title.value = `分队文字：${result.scrim.title}`
    text.value = result.copy_text
  } catch (failure) {
    showReadError(failure)
    error.value = failure instanceof Error ? failure.message : "暂时无法加载，请稍后再试。"
  } finally {
    pending.value = false
  }
}

async function copy(): Promise<void> {
  try {
    await navigator.clipboard.writeText(text.value)
    copied.value = "已复制分队文字。"
  } catch {
    copied.value = "无法自动复制，请选中文字复制。"
  }
}

onMounted(load)
</script>

<template>
  <AdminPage :title="title" section="events" :back-href="`/admin/scrims/${id}/split/`">
    <p v-if="pending" role="status">正在加载…</p>
    <AdminNotice v-else-if="error" :message="error" kind="error" />
    <template v-else>
      <pre>{{ text || '还没有分队结果。' }}</pre>
      <button type="button" class="c-btn c-btn--primary" :disabled="!text" @click="copy">复制文字</button>
      <p v-if="copied" role="status">{{ copied }}</p>
    </template>
    <button v-if="error" type="button" class="c-btn c-btn--secondary" @click="load">重试</button>
  </AdminPage>
</template>
