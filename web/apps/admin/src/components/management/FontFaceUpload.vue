<script setup lang="ts">
import { ref } from "vue"
import { useFontUpload } from "../../pages/management/use-font-upload"
import type { FontDetail } from "../../pages/management/pending"
import ActionState from "./ActionState.vue"
const props=defineProps<{id:number}>()
const emit=defineEmits<{changed:[result:FontDetail]}>()
const file=ref<File|null>(null),license=ref(false)
const upload=useFontUpload(result=>emit('changed',result),props.id)
async function submit(){const chosen=file.value;if(chosen && license.value)await upload.submit({file:chosen,license:license.value})}
function choose(event:Event){file.value=(event.target as HTMLInputElement).files?.[0]??null}
</script>
<template>
 <section class="b-section"><h2 class="b-section__title">添加字重</h2><p class="b-section__text">上传同一个字体家族的成品包，只添加其中还不存在的字重。新字体按已批准的离线工具切好后上传。</p><form class="b-form" @submit.prevent="submit"><div class="c-field"><label class="c-field__label" for="face-package">成品包</label><input id="face-package" type="file" accept=".zip" class="c-input" :disabled="!upload.canStart.value" @change="choose" /></div><label class="c-check"><input v-model="license" type="checkbox" :disabled="!upload.canStart.value" />我确认字体授权允许在本站使用</label><div class="b-actions"><button type="submit" class="c-btn c-btn--primary" :disabled="!file || !license || !upload.canStart.value">添加</button></div></form><p v-if="upload.pending.value" class="b-sub" role="status">{{ upload.stage.value }} {{ upload.progress.value }}%</p><ActionState :message="upload.message.value" :pending="upload.pending.value" :uncertain="upload.uncertain.value" @retry="upload.retry" /></section>
</template>
