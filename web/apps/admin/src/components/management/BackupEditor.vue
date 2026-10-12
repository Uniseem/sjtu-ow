<script setup lang="ts">
import { ref } from "vue"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { getBackup, testStorage } from "../../pages/management/pending"
import { useResource } from "../../pages/management/use-resource"
import BackupForm from "./BackupForm.vue"
import ResourceState from "./ResourceState.vue"
import ActionState from "./ActionState.vue"
const api = useAdminApi()
const resource = useResource(() => true, signal => getBackup(api, { signal }))
const message = ref("")
const form=ref<InstanceType<typeof BackupForm>|null>(null)
defineExpose({test:()=>form.value?.test()})
const action = useAdminAction<null, Awaited<ReturnType<typeof testStorage>>>((_, extras) => testStorage(api, extras), response => { message.value = response.message })
</script>
<template>
  <section class="b-section">
    <h2 class="b-section__title">异地备份（对象存储）</h2>
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <BackupForm ref="form" v-if="resource.data.value" :key="resource.data.value.version" :data="resource.data.value" @test="action.submit(null)" @changed="resource.refresh" />
    <p class="b-sub">测试对象存储：用已保存的异地备份设置往存储桶里写一个小文件再删掉，看能不能连上、有没有权限。刚改的设置会先存好再测；「备份上传到对象存储」没打开也能测。</p>
    <p v-if="message" class="b-sub" role="status">{{ message }}</p>
    <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
  </section>
</template>
