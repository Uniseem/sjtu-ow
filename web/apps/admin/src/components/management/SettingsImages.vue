<script setup lang="ts">
import { computed, ref, shallowRef,watch } from "vue"
import { getApiAdminImages, patchApiAdminSettings,ApiError, type GetApiAdminImagesOut } from "@sjtu-ow/api"
import { imageUrl } from "@sjtu-ow/shared/media"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import type { Settings } from "../../pages/management/settings-fields"
import ActionState from "./ActionState.vue"
const props = defineProps<{ settings: Settings; version:()=>number;beforeAction: () => Promise<boolean> }>()
const emit=defineEmits<{changed:[settings:Settings];settled:[]}>()
const api = useAdminApi()
type ImageKey = 'default_share_image_id' | 'hero_image_id' | 'banner_news_id' | 'banner_tournaments_id' | 'banner_scrims_id' | 'banner_teams_id' | 'banner_members_id'
const choices: { key: ImageKey; label: string }[] = [
  { key: 'default_share_image_id', label: '默认分享图片' }, { key: 'hero_image_id', label: '首页首屏图' },
  { key: 'banner_news_id', label: '资讯横幅' }, { key: 'banner_tournaments_id', label: '赛事横幅' },
  { key: 'banner_scrims_id', label: '内战横幅' }, { key: 'banner_teams_id', label: '战队横幅' }, { key: 'banner_members_id', label: '成员横幅' },
]
const values = shallowRef<Record<ImageKey, number | null>>({ default_share_image_id: props.settings.default_share_image_id, hero_image_id: props.settings.hero_image_id, banner_news_id: props.settings.banner_news_id, banner_tournaments_id: props.settings.banner_tournaments_id, banner_scrims_id: props.settings.banner_scrims_id, banner_teams_id: props.settings.banner_teams_id, banner_members_id: props.settings.banner_members_id })
const active = ref<ImageKey | null>(null)
const dialog = ref<HTMLDialogElement | null>(null)
const search = ref("")
const page = ref(1)
const images = shallowRef<GetApiAdminImagesOut | null>(null)
const loading = ref(false)
const error = ref("")
const label = computed(() => choices.find(choice => choice.key === active.value)?.label ?? '图片')
let revision = 0
const action = useAdminAction<{ key: ImageKey; id: number | null;version:number }, Awaited<ReturnType<typeof patchApiAdminSettings>>>((body, extras) => patchApiAdminSettings(api, {base_version:body.version,changes:{[body.key]:body.id??0}},extras), result => {
  if (result.settings) values.value = Object.fromEntries(choices.map(choice => [choice.key, result.settings![choice.key]])) as Record<ImageKey, number | null>
  if(result.settings)emit("changed",result.settings)
  if(!result.saved.length)throw new ApiError(422,"invalid_fields",Object.values(result.fields||{}).flat().join("；")||"图片尚未保存，请重试。")
  dialog.value?.close()
})
async function load() {
  const current = ++revision
  loading.value = true
  error.value = ""
  try { const result = await getApiAdminImages(api, { q: search.value, page: page.value, page_size: 48 }); if (current === revision) images.value = result }
  catch (failure) { if (current === revision) error.value = failure instanceof Error ? failure.message : '暂时无法加载图片。' }
  finally { if (current === revision) loading.value = false }
}
async function open(key: ImageKey) { active.value = key; search.value = ''; page.value = 1; dialog.value?.showModal(); await load() }
async function select(key: ImageKey, id: number | null) { if (await props.beforeAction()) await action.submit({ key, id,version:props.version() }) }
watch(()=>[action.pending.value,action.uncertain.value],([pending,uncertain])=>{if(!pending&&!uncertain)emit("settled")})
</script>
<template>
  <section class="b-section">
    <h2 class="b-section__title">图片</h2>
    <div v-for="choice in choices" :key="choice.key" class="c-field">
      <span class="c-field__label">{{ choice.label }}</span>
      <div class="b-picker">
        <img v-if="values[choice.key]" :src="imageUrl(values[choice.key]!, 'fill-960x540')" :alt="choice.label" width="180" height="120" loading="lazy" />
        <span v-else class="b-sub">未选择</span>
        <button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="!action.canStart.value" @click="open(choice.key)">选择</button>
        <button v-if="values[choice.key]" type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="!action.canStart.value" @click="select(choice.key, null)">清除</button>
      </div>
    </div>
    <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
    <dialog ref="dialog" class="b-dialog" aria-labelledby="settings-image-title">
      <h2 id="settings-image-title" class="b-section__title">选择{{ label }}</h2>
      <form class="b-filters" @submit.prevent="page = 1; load()">
        <input v-model="search" type="search" class="c-input" aria-label="搜图片标题" placeholder="搜标题" />
        <button class="c-btn c-btn--secondary c-btn--sm" :disabled="loading">搜索</button>
      </form>
      <p v-if="loading" class="b-sub" role="status">正在加载…</p>
      <p v-if="error" class="c-field__error" role="alert">{{ error }}</p>
      <div class="b-grid">
        <button v-for="image in images?.items" :key="image.id" type="button" class="b-grid__item" :disabled="!action.canStart.value" @click="active && select(active, image.id)">
          <img :src="imageUrl(image.id, 'fill-960x540')" :alt="image.title" width="160" height="110" loading="lazy" />
          <span>{{ image.title }}</span>
          <span class="b-sub">{{ image.width }} × {{ image.height }}</span>
        </button>
      </div>
      <div class="b-actions">
        <button v-if="page > 1" type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="loading" @click="page--; load()">上一页</button>
        <button v-if="images && page * images.page_size < images.total" type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="loading" @click="page++; load()">下一页</button>
        <button type="button" class="c-btn c-btn--quiet c-btn--sm" @click="dialog?.close()">取消</button>
      </div>
    </dialog>
  </section>
</template>
