<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRoute } from "vue-router"
import { getApiAdminArticlesId, type GetApiAdminArticlesIdOut } from "@sjtu-ow/api"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"

const route = useRoute()
const id = ref((route.params.id as string) || "")
const isNew = !id.value || id.value === "new"

const loading = ref(!isNew)
const saving = ref(false)
const message = ref<string | null>(null)
const error = ref<string | null>(null)

const title = ref("")
const slug = ref("")
const summary = ref("")
const content = ref("")
const status = ref("draft")

onMounted(async () => {
  if (!isNew) {
    try {
      const res = await getApiAdminArticlesId(id.value)
      if (res.article) {
        title.value = res.article.title
        slug.value = res.article.slug
        summary.value = res.article.summary ?? ""
        content.value = res.article.content ?? ""
        status.value = res.article.status
      }
    } catch (err: any) {
      error.value = err?.message ?? "加载文章失败"
    } finally {
      loading.value = false
    }
  }
})

async function saveDraft() {
  saving.value = true
  message.value = null
  error.value = null
  try {
    // 自动保存或手动保存草稿
    message.value = "草稿已保存"
  } catch (err: any) {
    error.value = err?.message ?? "保存失败"
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <AdminHead
      kicker="内容"
      :title="isNew ? '写新文章' : (title || '编辑文章')"
      back-to="/admin/articles/"
      back-label="返回文章列表"
    >
      <template #actions>
        <button class="c-btn c-btn--secondary c-btn--sm" :disabled="saving" @click="saveDraft">
          {{ saving ? '正在保存...' : '保存草稿' }}
        </button>
        <button class="c-btn c-btn--primary c-btn--sm">
          发布
        </button>
      </template>
    </AdminHead>

    <div class="b-main">
      <div v-if="message" class="c-notice c-notice--success mb-4">
        <p>{{ message }}</p>
      </div>
      <div v-if="error" class="c-notice c-notice--danger mb-4">
        <p>{{ error }}</p>
      </div>

      <div class="b-split grid grid-cols-1 lg:grid-cols-[1fr_22rem] gap-6">
        <!-- 左侧编辑表单 -->
        <div class="flex flex-col gap-4 bg-surface p-6 rounded-lg border border-border shadow-xs">
          <div>
            <label class="block text-sm font-semibold mb-1">文章标题</label>
            <input
              v-model="title"
              type="text"
              class="c-input w-full text-lg font-bold"
              placeholder="输入引人注目的标题..."
            />
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-semibold mb-1">网址片段 (Slug)</label>
              <input
                v-model="slug"
                type="text"
                class="c-input w-full"
                placeholder="留空自动根据标题生成"
              />
            </div>
            <div>
              <label class="block text-sm font-semibold mb-1">分类</label>
              <select class="c-input w-full">
                <option value="">社区快讯</option>
                <option value="">赛事战报</option>
                <option value="">攻略心得</option>
              </select>
            </div>
          </div>

          <div>
            <label class="block text-sm font-semibold mb-1">文章摘要</label>
            <textarea
              v-model="summary"
              rows="2"
              class="c-input w-full resize-y"
              placeholder="简短的摘要介绍，用于列表展示与 SEO 检索..."
            />
          </div>

          <div>
            <label class="block text-sm font-semibold mb-1">正文 (Markdown)</label>
            <textarea
              v-model="content"
              rows="16"
              class="c-input w-full font-mono text-sm resize-y leading-relaxed"
              placeholder="在此编写 Markdown 格式的正文内容..."
            />
          </div>
        </div>

        <!-- 右侧状态栏 b-aside -->
        <aside class="b-aside flex flex-col gap-4">
          <div class="b-section p-5 rounded-lg bg-surface border border-border shadow-xs">
            <h3 class="font-bold text-sm mb-3 pb-2 border-b border-border">发布状态</h3>
            <div class="space-y-2 text-xs text-fg-2">
              <div class="flex justify-between">
                <span>当前状态：</span>
                <span class="font-semibold text-fg">{{ status === 'published' ? '已发布' : '草稿' }}</span>
              </div>
              <div class="flex justify-between">
                <span>评论设置：</span>
                <span class="font-semibold text-fg">开放评论</span>
              </div>
            </div>

            <div class="mt-4 pt-3 border-t border-border flex flex-col gap-2">
              <button class="c-btn c-btn--primary w-full c-btn--sm">
                {{ status === 'published' ? '更新发布' : '立即发布' }}
              </button>
              <button v-if="status === 'published'" class="c-btn c-btn--secondary w-full c-btn--sm">
                撤下文章
              </button>
              <button v-if="!isNew" class="c-btn c-btn--ghost w-full c-btn--sm text-danger">
                删除草稿
              </button>
            </div>
          </div>

          <div class="b-section p-5 rounded-lg bg-surface border border-border shadow-xs">
            <h3 class="font-bold text-sm mb-3 pb-2 border-b border-border">封面图</h3>
            <div class="p-6 border-2 border-dashed border-border rounded-md text-center">
              <CIcon name="settings" class="size-8 mx-auto text-fg-3 mb-2" />
              <p class="text-xs text-fg-3">暂无封面图</p>
              <a href="/admin/images/" class="c-btn c-btn--secondary c-btn--xs mt-2">从图片库选择</a>
            </div>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>
