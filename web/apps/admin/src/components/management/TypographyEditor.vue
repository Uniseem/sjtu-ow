<script setup lang="ts">
import { computed } from "vue"
import { postApiAdminTypographyPreview } from "@sjtu-ow/api"
import { useHead } from "@unhead/vue"
import { useAdminApi } from "../../core/api"
import { useAdminSave } from "../../core/use-save"
import { patchTypography, fullRegion, type TypographyPage, type TypographyValues, type TypographyRegionValues } from "../../pages/management/pending"
import { currentReader } from "../../pages/management/current-reader"
import { useResource } from "../../pages/management/use-resource"
import { date } from "../../pages/management/format"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import SaveStatus from "../SaveStatus.vue"
const props = defineProps<{ data: TypographyPage }>()
const api = useAdminApi()
function editable(row: TypographyRegionValues): TypographyRegionValues {
  return { region: row.region, mode: row.mode, family_id: row.family_id, weight: row.weight,
    size_rem: row.size_rem, line_height: row.line_height, letter_spacing_em: row.letter_spacing_em }
}
const initial: TypographyValues = { regions: props.data.regions.map(editable) }
const save = useAdminSave<TypographyValues>({ initial, version: props.data.version, readCurrent: currentReader(initial),
  transport: (body, key, signal) => patchTypography(api, body, { key, signal }) })
const rows = computed(() => save.values.value.regions)
const preview = useResource(() => JSON.stringify(rows.value), signal => postApiAdminTypographyPreview(api, { regions: rows.value.map(fullRegion) }, { signal }), 600, false)
useHead(() => ({ link: preview.data.value?.css_path.startsWith('/media/fonts/css/preview.')
  ? [{ rel: 'stylesheet', href: preview.data.value.css_path }] : [] }))
function update(region: string, key: keyof TypographyRegionValues, event: Event) {
  const value = (event.target as HTMLInputElement).value
  const next = rows.value.map(row => {
    if (row.region !== region) return row
    if (key === 'family_id') return { ...row, family_id: value ? Number(value) : null }
    if (key === 'mode') return { ...row, mode: value as TypographyRegionValues['mode'] }
    if (key === 'weight') return { ...row, weight: Number(value) }
    if (key === 'size_rem' || key === 'line_height' || key === 'letter_spacing_em') return { ...row, [key]: value === '' ? null : Number(value) }
    return row
  })
  save.set('regions', next, key === 'mode' || key === 'family_id' || key === 'weight' ? 'choice' : 'text')
}
function effectiveID(row: TypographyRegionValues) {
  return row.mode === 'inherit' ? rows.value.find(item => item.region === 'body')?.family_id : row.mode === 'custom' ? row.family_id : null
}
function weights(row: TypographyRegionValues) { return props.data.fonts.find(font => font.id === effectiveID(row))?.weights ?? [100, 200, 300, 400, 500, 600, 700, 800, 900] }
function label(region: string) { return props.data.regions.find(row => row.region === region)?.label ?? region }
const numericFields = [{ key: 'size_rem', label: '字号（rem）', step: '0.001' }, { key: 'line_height', label: '行高（倍）', step: '0.01' }, { key: 'letter_spacing_em', label: '字间距（em）', step: '0.001' }] as const
</script>
<template>
  <div v-for="warning in data.warnings" :key="warning" class="c-notice c-notice--warn"><CIcon name="alert" /><div class="c-notice__body">{{ warning }}</div></div>
  <p v-if="data.css_path" class="b-section__text">当前字体样式表：<span class="b-mono">{{ data.css_path }}</span>（{{ date(data.generated_at) }}）</p>
  <p v-else class="b-section__text">还没有生成字体样式表，全站使用系统字体。</p>
  <div class="typography-layout">
    <form class="b-form" @submit.prevent="save.save">
      <div class="b-fieldset">
        <section v-for="row in rows" :key="row.region" class="typography-row" :data-region="row.region">
          <h2 class="b-section__title">{{ label(row.region) }}</h2><p v-if="data.regions.find(region=>region.region===row.region)?.slices" class="b-sub">当前字重：{{ data.regions.find(region=>region.region===row.region)?.slices }} 个分片，合计 {{ data.regions.find(region=>region.region===row.region)?.bytes }} bytes</p>
          <div class="c-field">
            <label class="c-field__label" :for="`type-mode-${row.region}`">字体来源</label>
            <select :id="`type-mode-${row.region}`" class="c-input" :value="row.mode" @change="update(row.region, 'mode', $event)">
              <option value="system">系统字体</option>
              <option v-if="row.region !== 'body'" value="inherit">跟随正文</option>
              <option value="custom">字体库中的字体</option>
            </select>
          </div>
          <div v-if="row.mode === 'custom'" class="c-field">
            <label class="c-field__label" :for="`type-family-${row.region}`">字体</label>
            <select :id="`type-family-${row.region}`" class="c-input" :value="row.family_id ?? ''" @change="update(row.region, 'family_id', $event)">
              <option value="">（未选择）</option>
              <option v-for="font in data.fonts" :key="font.id" :value="font.id">{{ font.display_name || font.family }}</option>
            </select>
          </div>
          <div class="c-field">
            <label class="c-field__label" :for="`type-weight-${row.region}`">字重</label>
            <select :id="`type-weight-${row.region}`" class="c-input" :value="row.weight" @change="update(row.region, 'weight', $event)">
              <option v-for="weight in weights(row)" :key="weight" :value="weight">{{ weight }}</option>
              <option v-if="!weights(row).includes(row.weight)" :value="row.weight">{{ row.weight }}（没有可用分片）</option>
            </select>
          </div>
          <div v-for="field in numericFields" :key="field.key" class="c-field">
            <label class="c-field__label" :for="`type-${field.key}-${row.region}`">{{ field.label }}</label>
            <input :id="`type-${field.key}-${row.region}`" class="c-input" type="number" :step="field.step" :value="row[field.key] ?? ''" @input="update(row.region, field.key, $event)" @blur="save.flush" />
          </div>
        </section>
      </div>
      <p v-for="error in save.fields.value.regions" :key="error" class="c-field__error" role="alert">{{ error }}</p>
      <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
      <div class="b-formbar">
        <button class="c-btn c-btn--primary" :disabled="save.pending.value">保存并生成样式表</button>
        <RouterLink to="/admin/settings/fonts/" class="c-btn c-btn--secondary">返回字体库</RouterLink>
      </div>
    </form>
    <aside class="typography-aside" aria-labelledby="typography-preview-heading">
      <h2 id="typography-preview-heading" class="b-section__title">实时预览</h2>
      <p class="b-sub">预览随表单变化；改动自动保存后，前台一两分钟内跟着更新。</p>
      <p v-if="preview.pending.value" class="b-sub" role="status">正在生成预览…</p>
      <p v-if="preview.message.value" class="c-field__error" role="alert">{{ preview.message.value }}</p>
      <div id="typography-preview">
        <div class="p-nav"><span>首页</span><span>资讯</span><span>赛事</span><span>成员</span></div>
        <h1 class="p-h1">SJTU-OW 上海交通大学守望先锋 2026 钻石 3 · Genji#51234</h1>
        <h2 class="p-h2">赛事公告：2026 春季赛报名开启</h2>
        <p >正文示例：本次比赛面向全体交大学生与校友，报名时请填写一个游戏 ID 与一种联系方式。守望先锋，启动。</p>
        <h3 class="p-h3">分组结果</h3>
        <p class="p-code">Genji#51234 · Tracer#12345 · 分队 A</p>
        <h4 class="p-h4">数据</h4>
        <p class="p-numeric">钻石 3 · 3250 分 · 12 胜 8 负 · 2026-09-16 19:30</p>
        <p><button type="button" class="p-button">报名</button></p>
      </div>
    </aside>
  </div>
</template>
