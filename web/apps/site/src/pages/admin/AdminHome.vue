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
const todo = ref<GetApiAdminTodoOut["todo"] | null>(null)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    const res = await getApiAdminTodo(api)
    todo.value = res.todo
  } catch (err: any) {
    error.value = err?.message ?? "加载待办失败"
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <AdminHead kicker="首页" title="管理后台首页">
      <template #actions>
        <a href="/" class="c-btn c-btn--secondary c-btn--sm">
          <CIcon name="arrow-up-right" class="size-4 mr-1" /> 打开网站
        </a>
      </template>
    </AdminHead>

    <div class="b-main">
      <!-- 问候卡片 -->
      <section class="b-section p-6 rounded-lg bg-surface border border-border shadow-xs">
        <h2 class="text-xl font-bold text-fg">
          你好，{{ viewer.user?.nickname ?? "干部" }}！
        </h2>
        <p class="mt-2 text-sm text-fg-2">
          欢迎回到 SJTU-OW 管理后台。你可以在这里处理日常社区事务、赛事编排与全站运维。
        </p>

        <!-- 快捷操作入口 -->
        <div class="mt-5 flex flex-wrap gap-3">
          <a href="/admin/articles/new/" class="c-btn c-btn--primary c-btn--sm">
            <CIcon name="pen" class="size-4 mr-1" /> 写文章
          </a>
          <a href="/admin/tournaments/new/" class="c-btn c-btn--secondary c-btn--sm">
            <CIcon name="trophy" class="size-4 mr-1" /> 新建赛事
          </a>
          <a href="/admin/scrims/new/" class="c-btn c-btn--secondary c-btn--sm">
            <CIcon name="shield" class="size-4 mr-1" /> 新建内战
          </a>
          <a href="/admin/letters/" class="c-btn c-btn--ghost c-btn--sm">
            <CIcon name="mail" class="size-4 mr-1" /> 待发信管理
          </a>
        </div>
      </section>

      <!-- 待办事项 -->
      <section class="b-section p-6 rounded-lg bg-surface border border-border shadow-xs">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-bold text-fg flex items-center gap-2">
            <CIcon name="check-circle" class="size-5 text-accent" /> 干部待办
          </h2>
          <span v-if="loading" class="text-xs text-fg-3">正在拉取待办...</span>
        </div>

        <div v-if="error" class="c-notice c-notice--warning mb-4">
          <p>{{ error }}</p>
        </div>

        <div v-else-if="!loading && todo" class="grid gap-3">
          <!-- 待确认发信批次 -->
          <div v-if="todo.pending_held_batches > 0" class="flex items-center justify-between p-3 rounded-md bg-surface-2 border border-border">
            <div class="flex items-center gap-3">
              <span class="inline-flex items-center justify-center size-8 rounded-full bg-primary-soft text-on-primary-soft font-bold text-sm">
                {{ todo.pending_held_batches }}
              </span>
              <div>
                <p class="font-medium text-fg">有待确认的发信批次</p>
                <p class="text-xs text-fg-2">操作顺带产生的邮件等待发送确认</p>
              </div>
            </div>
            <a href="/admin/letters/" class="c-btn c-btn--sm c-btn--primary">前往确认</a>
          </div>

          <!-- 待审核赛事报名 -->
          <div v-if="todo.unreviewed_registrations > 0" class="flex items-center justify-between p-3 rounded-md bg-surface-2 border border-border">
            <div class="flex items-center gap-3">
              <span class="inline-flex items-center justify-center size-8 rounded-full bg-accent-soft text-on-accent-soft font-bold text-sm">
                {{ todo.unreviewed_registrations }}
              </span>
              <div>
                <p class="font-medium text-fg">赛事报名待审核</p>
                <p class="text-xs text-fg-2">有新队伍或个人提交了赛事报名申请</p>
              </div>
            </div>
            <a href="/admin/registrations/" class="c-btn c-btn--sm c-btn--secondary">去审核</a>
          </div>

          <!-- 待编排散人 -->
          <div v-if="todo.pending_individual_signups > 0" class="flex items-center justify-between p-3 rounded-md bg-surface-2 border border-border">
            <div class="flex items-center gap-3">
              <span class="inline-flex items-center justify-center size-8 rounded-full bg-warning-soft text-on-warning-soft font-bold text-sm">
                {{ todo.pending_individual_signups }}
              </span>
              <div>
                <p class="font-medium text-fg">散人池待编排</p>
                <p class="text-xs text-fg-2">散人个人报名待组成临时队伍参赛</p>
              </div>
            </div>
            <a href="/admin/tournaments/" class="c-btn c-btn--sm c-btn--secondary">编排队伍</a>
          </div>

          <!-- 未分队内战 -->
          <div v-if="todo.unsplit_scrims > 0" class="flex items-center justify-between p-3 rounded-md bg-surface-2 border border-border">
            <div class="flex items-center gap-3">
              <span class="inline-flex items-center justify-center size-8 rounded-full bg-primary-soft text-on-primary-soft font-bold text-sm">
                {{ todo.unsplit_scrims }}
              </span>
              <div>
                <p class="font-medium text-fg">内战尚未分队</p>
                <p class="text-xs text-fg-2">已有报名人员，等待干部排布阵容或算法分队</p>
              </div>
            </div>
            <a href="/admin/scrims/" class="c-btn c-btn--sm c-btn--secondary">去分队</a>
          </div>

          <!-- 无队长战队 -->
          <div v-if="todo.teams_without_captain > 0" class="flex items-center justify-between p-3 rounded-md bg-surface-2 border border-border">
            <div class="flex items-center gap-3">
              <span class="inline-flex items-center justify-center size-8 rounded-full bg-danger-soft text-on-danger-soft font-bold text-sm">
                {{ todo.teams_without_captain }}
              </span>
              <div>
                <p class="font-medium text-fg">存在无队长战队</p>
                <p class="text-xs text-fg-2">队长已注销或停用，需管理员手动指定新队长</p>
              </div>
            </div>
            <a href="/admin/teams/" class="c-btn c-btn--sm c-btn--secondary">处理战队</a>
          </div>

          <!-- AI 巡查异常 -->
          <div v-if="todo.moderation_anomalies > 0" class="flex items-center justify-between p-3 rounded-md bg-surface-2 border border-border">
            <div class="flex items-center gap-3">
              <span class="inline-flex items-center justify-center size-8 rounded-full bg-danger-soft text-on-danger-soft font-bold text-sm">
                {{ todo.moderation_anomalies }}
              </span>
              <div>
                <p class="font-medium text-fg">AI 内容巡查发现可疑记录</p>
                <p class="text-xs text-fg-2">有新发布的内容被标记为待人工复核</p>
              </div>
            </div>
            <a href="/admin/moderation/" class="c-btn c-btn--sm c-btn--danger">去复核</a>
          </div>

          <!-- 全空状态 -->
          <div
            v-if="
              todo.pending_held_batches === 0 &&
              todo.unreviewed_registrations === 0 &&
              todo.pending_individual_signups === 0 &&
              todo.unsplit_scrims === 0 &&
              todo.teams_without_captain === 0 &&
              todo.moderation_anomalies === 0
            "
            class="text-center py-8 text-fg-3"
          >
            <CIcon name="check" class="size-8 mx-auto mb-2 text-success opacity-80" />
            <p>目前一切安好，暂时没有需要处理的待办事项！</p>
          </div>
        </div>

        <!-- 底部 Worker 存活状态 -->
        <div v-if="todo" class="mt-6 pt-4 border-t border-border flex items-center justify-between text-xs text-fg-3">
          <span>Worker 进程状态：
            <span :class="todo.worker_alive ? 'text-success font-semibold' : 'text-danger font-semibold'">
              {{ todo.worker_alive ? '正常运行中' : '未检测到心跳' }}
            </span>
          </span>
          <span v-if="todo.worker_heartbeat_at">上次心跳：{{ todo.worker_heartbeat_at }}</span>
        </div>
      </section>
    </div>
  </div>
</template>
