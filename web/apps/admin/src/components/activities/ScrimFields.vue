<script setup lang="ts">
import type { ScrimValues } from "../../pages/activities/form-schema"
import { formatOptions, keepSeconds, localMinute } from "../../pages/activities/domain"
import ActivityField from "./ActivityField.vue"
import MarkdownEditor from "../content/MarkdownEditor.vue"

const props = defineProps<{
  values: ScrimValues
  committed: ScrimValues
  fields: Record<string, string[]>
  disabled: boolean
}>()
const emit = defineEmits<{
  change: [name: keyof ScrimValues, value: string | boolean | null, kind: "text" | "choice"]
  blur: []
}>()

function text(name: "title" | "description", event: Event): void {
  if (!(event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement)) return
  emit("change", name, event.target.value, "text")
}

function date(name: "starts_at" | "signup_closes_at", event: Event): void {
  if (!(event.target instanceof HTMLInputElement)) return
  emit("change", name, keepSeconds(event.target.value, props.committed[name]), "text")
}

function format(event: Event): void {
  if (!(event.target instanceof HTMLSelectElement)) return
  emit("change", "format", event.target.value, "choice")
}

function check(event: Event): void {
  if (!(event.target instanceof HTMLInputElement)) return
  emit("change", "sjtu_only", event.target.checked, "choice")
}
</script>

<template>
  <fieldset class="b-section" :disabled="disabled">
    <legend class="b-section__title">内容</legend>
    <ActivityField id="title" label="标题" :errors="fields.title" required v-slot="field">
      <input
        id="title"
        name="title"
        type="text"
        class="c-input"
        maxlength="100"
        :value="values.title"
        :aria-invalid="Boolean(fields.title?.length)"
        :aria-describedby="field.describedby"
        @input="text('title', $event)"
        @blur="emit('blur')"
      >
    </ActivityField>
    <ActivityField id="description" label="说明" help="支持 Markdown。" :errors="fields.description" v-slot="field">
      <MarkdownEditor
        id="description"
        name="description"
        label="说明"
        :model-value="values.description"
        :disabled="disabled"
        :describedby="field.describedby"
        :invalid="Boolean(fields.description?.length)"
        @update:model-value="emit('change', 'description', $event, 'text')"
        @blur="emit('blur')"
      />
    </ActivityField>
  </fieldset>
  <fieldset class="b-section" :disabled="disabled">
    <legend class="b-section__title">时间</legend>
    <ActivityField id="starts_at" label="开始时间" help="北京时间；只修改到分钟。" :errors="fields.starts_at" required v-slot="field">
      <input
        id="starts_at"
        name="starts_at"
        type="datetime-local"
        class="c-input"
        step="60"
        :value="localMinute(values.starts_at)"
        :aria-invalid="Boolean(fields.starts_at?.length)"
        :aria-describedby="field.describedby"
        @input="date('starts_at', $event)"
        @blur="emit('blur')"
      >
    </ActivityField>
    <ActivityField id="signup_closes_at" label="报名截止时间" help="留空表示开始前都可以报名。" :errors="fields.signup_closes_at" v-slot="field">
      <input
        id="signup_closes_at"
        name="signup_closes_at"
        type="datetime-local"
        class="c-input"
        step="60"
        :value="localMinute(values.signup_closes_at)"
        :aria-invalid="Boolean(fields.signup_closes_at?.length)"
        :aria-describedby="field.describedby"
        @input="date('signup_closes_at', $event)"
        @blur="emit('blur')"
      >
    </ActivityField>
  </fieldset>
  <fieldset class="b-section" :disabled="disabled">
    <legend class="b-section__title">规则</legend>
    <ActivityField id="format" label="规格" :errors="fields.format" v-slot="field">
      <select
        id="format"
        name="format"
        class="c-input"
        :value="values.format"
        :aria-invalid="Boolean(fields.format?.length)"
        :aria-describedby="field.describedby"
        @change="format"
      >
        <option v-for="option in formatOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
    </ActivityField>
    <ActivityField id="sjtu_only" label="仅限交大" :errors="fields.sjtu_only" v-slot="field">
      <label class="c-check">
        <input
          id="sjtu_only"
          name="sjtu_only"
          type="checkbox"
          :checked="values.sjtu_only"
          :aria-invalid="Boolean(fields.sjtu_only?.length)"
          :aria-describedby="field.describedby"
          @change="check"
        >仅限交大
      </label>
    </ActivityField>
  </fieldset>
</template>
