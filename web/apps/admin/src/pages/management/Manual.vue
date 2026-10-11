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
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" :empty="!resource.data.value?.parts.length" empty-text="没有与你的权限相关的手册内容。" @retry="resource.refresh" />
    <nav v-if="resource.data.value?.parts.length" class="b-chips" aria-label="手册目录">
      <a v-for="part in resource.data.value.parts" :key="part.key" class="c-link" :href="`#manual-${part.key}`">{{ part.title }}</a>
    </nav>
    <section v-for="part in resource.data.value?.parts" :id="`manual-${part.key}`" :key="part.key" class="b-section">
      <h2 class="b-section__title">{{ part.title }}</h2>
      <ol class="b-steps">
        <li v-for="(step, index) in part.steps" :key="index">{{ step.text }}<a v-if="step.link_url && localHref(step.link_url)" class="c-link" :href="localHref(step.link_url)">{{ step.link_label || '打开' }} →</a>
        </li>
      </ol>
    </section>
  </AdminPage>
</template>
