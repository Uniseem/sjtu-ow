<script setup lang="ts">
import { getApiAdminManual } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import { localHref } from "./format"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
const api = useAdminApi()
const resource = useResource(() => true, signal => getApiAdminManual(api, { signal }))
</script>
<template>
  <AdminPage title="后台手册" section="手册">
    <p class="b-section__text">下面只列和你的身份有关的部分。每一步写了做什么、在哪儿、会发生什么。</p>
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" :empty="!resource.data.value?.parts.length" empty-text="没有与你的权限相关的手册内容。" @retry="resource.refresh" />
    <nav v-if="(resource.data.value?.parts.length ?? 0) > 1" class="b-chips" aria-label="目录">
      <a v-for="part in resource.data.value?.parts" :key="part.key" :href="`#manual-${part.key}`">{{ part.title }}</a>
    </nav>
    <section v-for="part in resource.data.value?.parts" :id="`manual-${part.key}`" :key="part.key" class="b-section" :data-manual-part="part.key">
      <h2 class="b-section__title">{{ part.title }}</h2>
      <ol class="b-steps">
        <li v-for="(step, index) in part.steps" :key="index">{{ step.text }}<a v-if="step.link_url && localHref(step.link_url)" class="c-link" :href="localHref(step.link_url)">{{ step.link_label || '打开' }} →</a>
        </li>
      </ol>
    </section>
  </AdminPage>
</template>
