<script setup lang="ts">
import { getHome } from "./pending"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import { localHref, state } from "./format"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import SetupList from "../../components/management/SetupList.vue"
const api = useAdminApi()
const resource = useResource(() => true, signal => getHome(api, { signal }))
</script>
<template>
  <AdminPage :title="resource.data.value ? `你好，${resource.data.value.nickname}` : '首页'" section="首页">
    <template #actions>
      <template v-for="action in resource.data.value?.actions" :key="action.url">
        <a v-if="localHref(action.url)" :href="localHref(action.url)" class="c-btn c-btn--sm" :class="action.primary ? 'c-btn--primary' : 'c-btn--secondary'" :target="action.url === '/' ? '_blank' : undefined" :rel="action.url === '/' ? 'noopener' : undefined" data-home-action>{{ action.label }}</a>
      </template>
    </template>
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <template v-if="resource.data.value">
      <p v-if="resource.data.value.roles.length" class="b-hello__roles">{{ resource.data.value.roles.join('、') }}</p>
      <section v-if="resource.data.value.has_duties" class="b-form" aria-labelledby="todo-heading" data-todo>
        <h2 id="todo-heading" class="b-section__title">待办<span v-if="resource.data.value.todo.length" class="b-count">{{ resource.data.value.todo.length }} 件</span>
        </h2>
        <div v-if="resource.data.value.todo.length" class="b-cards">
          <template v-for="(row, index) in resource.data.value.todo" :key="index">
            <a v-if="row.url && localHref(row.url)" class="b-card" :href="localHref(row.url)" data-todo-row>
              <span v-if="row.count > 1" class="b-card__count">{{ row.count }}</span>
              <span class="b-card__text">{{ row.text }}</span>
              <span class="b-card__go">去处理 →</span>
            </a>
            <div v-else class="b-card" data-todo-row>
              <span v-if="row.count > 1" class="b-card__count">{{ row.count }}</span>
              <span class="b-card__text">{{ row.text }}</span>
            </div>
          </template>
        </div>
        <p v-else class="b-section__text">暂时没有待办。</p>
      </section>
      <section class="b-section" aria-labelledby="mine-heading" data-my-articles>
        <div class="c-panel__head">
          <h2 id="mine-heading" class="b-section__title">我的文章</h2>
          <RouterLink class="c-btn c-btn--quiet c-btn--sm" to="/admin/articles/?mine=1">全部 →</RouterLink>
        </div>
        <ul v-if="resource.data.value.articles.length" class="b-list">
          <li v-for="article in resource.data.value.articles" :key="article.id">
            <RouterLink class="b-title" :to="`/admin/articles/${article.id}/`">{{ article.title || '（无标题）' }}</RouterLink>
            <CStatus :label="state(article.status)" :kind="article.status === 'draft' ? 'off' : article.status === 'scheduled' ? 'warn' : 'ok'" />
          </li>
        </ul>
        <p v-else class="b-section__text">还没写过文章。<template v-for="action in resource.data.value.actions" :key="action.url"><a v-if="action.label === '写文章'" class="c-link" :href="action.url">写一篇</a></template></p>
      </section>
      <section v-if="resource.data.value.setup" class="b-section" aria-labelledby="setup-heading" data-setup-list>
        <h2 id="setup-heading" class="b-section__title">上线清单<span class="b-count">只有超级管理员看得到</span>
        </h2>
        <p v-if="!resource.data.value.setup.required.length && !resource.data.value.setup.optional.length" class="b-section__text">都完成了。</p>
        <template v-else>
          <p class="b-section__text">
            <strong v-if="resource.data.value.setup.required.length">还有 {{ resource.data.value.setup.required.length }} 项必做</strong>
            <span v-if="resource.data.value.setup.required.length && resource.data.value.setup.optional.length">，</span><span v-if="resource.data.value.setup.optional.length">{{ resource.data.value.setup.optional.length }} 项建议做</span>。
          </p>
          <SetupList :items="resource.data.value.setup.required" kind="required" />
          <details v-if="resource.data.value.setup.optional.length" :open="!resource.data.value.setup.required.length">
            <summary class="c-link">建议做的 {{ resource.data.value.setup.optional.length }} 项</summary>
            <SetupList :items="resource.data.value.setup.optional" kind="optional" />
          </details>
        </template>
        <details v-if="resource.data.value.setup.done.length">
          <summary class="c-link">已完成 {{ resource.data.value.setup.done.length }} 项</summary>
          <SetupList :items="resource.data.value.setup.done" kind="done" />
        </details>
      </section>
    </template>
  </AdminPage>
</template>
