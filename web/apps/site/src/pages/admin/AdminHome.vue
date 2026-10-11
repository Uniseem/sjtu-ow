<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useViewer } from "../../viewer"
import { getApiAdminTodo, type GetApiAdminTodoOut } from "@sjtu-ow/api"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"
import { useApi } from "../../api"

const api = useApi()

const viewer = useViewer()
const loading = ref(true)
const todo = ref<GetApiAdminTodoOut["items"]>([])
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    const res = await getApiAdminTodo(api)
    todo.value = res.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : "加载待办失败"
  } finally {
    loading.value = false
  }
})
</script>
<template>
  <div><AdminHead kicker="工作台" title="管理后台首页" />
    <div class="b-main">
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-else-if="loading">正在加载待办事项...</p>
      <ul v-else-if="todo.length" class="c-rows"><li v-for="item in todo" :key="item.url" class="c-row"><a :href="item.url">{{ item.text }}</a><span>{{ item.count }}</span></li></ul>
      <p v-else>暂无待办事项。</p>
    </div>
  </div>
</template>
