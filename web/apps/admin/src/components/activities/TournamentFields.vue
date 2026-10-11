<script setup lang="ts">
import type { TournamentValues } from "../../pages/activities/form-schema"
import { keepSeconds, localMinute, modeOptions } from "../../pages/activities/domain"
import ActivityField from "./ActivityField.vue"
import MarkdownEditor from "../content/MarkdownEditor.vue"
import ImageField from "../content/ImageField.vue"

const props = defineProps<{
  values: TournamentValues
  committed: TournamentValues
  fields: Record<string, string[]>
  disabled: boolean
  hasEntries: boolean
  hasRegistrations: boolean
  teamMaximum: number | null
}>()
const emit = defineEmits<{
  change: [name: keyof TournamentValues, value: string | number | boolean | null, kind: "text" | "choice"]
  blur: []
}>()

function text(name: keyof TournamentValues, event: Event): void {
  if (!(event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement)) return
  emit("change", name, event.target.value, "text")
}

function choice(name: keyof TournamentValues, event: Event): void {
  if (!(event.target instanceof HTMLSelectElement)) return
  emit("change", name, event.target.value, "choice")
}

function number(name: "roster_min" | "roster_max", event: Event): void {
  if (!(event.target instanceof HTMLInputElement)) return
  if (!Number.isFinite(event.target.valueAsNumber)) {
    if (!event.target.value) emit("change", name, 0, "text")
    return
  }
  emit("change", name, event.target.valueAsNumber, "text")
}

function check(name: "sjtu_only" | "auto_approve", event: Event): void {
  if (!(event.target instanceof HTMLInputElement)) return
  emit("change", name, event.target.checked, "choice")
}

function date(name: "starts_at" | "registration_opens_at" | "registration_closes_at", event: Event): void {
  if (!(event.target instanceof HTMLInputElement)) return
  emit("change", name, keepSeconds(event.target.value, props.committed[name]), "text")
}
</script>

<template>
  <fieldset class="b-section" :disabled="disabled">
    <legend class="b-section__title">内容</legend>
    <ActivityField id="title" label="标题" :errors="fields.title" required v-slot="field">
      <input
        id="title"
        name="title"
        class="c-input"
        type="text"
        maxlength="100"
        :value="values.title"
        :aria-invalid="Boolean(fields.title?.length)"
        :aria-describedby="field.describedby"
        @input="text('title', $event)"
        @blur="emit('blur')"
      >
    </ActivityField>
    <ActivityField id="summary" label="简介" :errors="fields.summary" v-slot="field">
      <textarea
        id="summary"
        name="summary"
        class="c-input"
        rows="2"
        maxlength="300"
        :value="values.summary"
        :aria-invalid="Boolean(fields.summary?.length)"
        :aria-describedby="field.describedby"
        @input="text('summary', $event)"
        @blur="emit('blur')"
      />
    </ActivityField>
    <ActivityField id="description" label="详细说明" :errors="fields.description" help="支持 Markdown。" v-slot="field">
      <MarkdownEditor
        id="description"
        label="详细说明"
        :model-value="values.description"
        :disabled="disabled"
        :describedby="field.describedby"
        :invalid="Boolean(fields.description?.length)"
        @update:model-value="emit('change', 'description', $event, 'text')"
        @blur="emit('blur')"
      />
    </ActivityField>
    <ActivityField id="cover" label="封面" :errors="fields.cover_image_id">
      <ImageField
        name="cover_image_id"
        label="封面"
        :model-value="values.cover_image_id"
        :disabled="disabled"
        @update:model-value="emit('change', 'cover_image_id', $event, 'choice')"
      />

    </ActivityField>
  </fieldset>

  <fieldset class="b-section" :disabled="disabled">
    <legend class="b-section__title">时间</legend>
    <ActivityField id="starts_at" label="比赛时间" :errors="fields.starts_at" help="北京时间；只修改到分钟。" v-slot="field">
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
    <ActivityField id="registration_opens_at" label="报名开始时间" :errors="fields.registration_opens_at" required v-slot="field">
      <input
        id="registration_opens_at"
        name="registration_opens_at"
        type="datetime-local"
        class="c-input"
        step="60"
        :value="localMinute(values.registration_opens_at)"
        :aria-invalid="Boolean(fields.registration_opens_at?.length)"
        :aria-describedby="field.describedby"
        @input="date('registration_opens_at', $event)"
        @blur="emit('blur')"
      >
    </ActivityField>
    <ActivityField id="registration_closes_at" label="报名截止时间" :errors="fields.registration_closes_at" required v-slot="field">
      <input
        id="registration_closes_at"
        name="registration_closes_at"
        type="datetime-local"
        class="c-input"
        step="60"
        :value="localMinute(values.registration_closes_at)"
        :aria-invalid="Boolean(fields.registration_closes_at?.length)"
        :aria-describedby="field.describedby"
        @input="date('registration_closes_at', $event)"
        @blur="emit('blur')"
      >
    </ActivityField>
  </fieldset>

  <fieldset class="b-section" :disabled="disabled">
    <legend class="b-section__title">报名规则</legend>
    <ActivityField
      id="registration_mode"
      label="报名方式"
      :errors="fields.registration_mode"
      :help="hasEntries ? '已经有人报名了，不能再改「报名方式」。' : ''"
      v-slot="field"
    >
      <select
        id="registration_mode"
        name="registration_mode"
        class="c-input"
        :value="values.registration_mode"
        :disabled="disabled || hasEntries"
        :aria-describedby="field.describedby"
        :aria-invalid="Boolean(fields.registration_mode?.length)"
        @change="choice('registration_mode', $event)"
      >
        <option v-for="option in modeOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
    </ActivityField>
    <ActivityField
      id="roster_min"
      label="参赛人数下限"
      :errors="fields.roster_min"
      :help="teamMaximum === null ? '整队报名时不能超过全站战队人数上限；个人报名不受这条限制。' : `整队报名时不能超过全站战队人数上限（现在是 ${teamMaximum} 人，在全站设置里改），否则没有战队能报名。个人报名不受这条限制。`"
      v-slot="field"
    >
      <input
        id="roster_min"
        name="roster_min"
        type="number"
        class="c-input"
        min="1"
        max="20"
        step="1"
        :value="values.roster_min"
        :aria-describedby="field.describedby"
        :aria-invalid="Boolean(fields.roster_min?.length)"
        @input="number('roster_min', $event)"
        @blur="emit('blur')"
      >
    </ActivityField>
    <ActivityField id="roster_max" label="参赛人数上限" :errors="fields.roster_max" v-slot="field">
      <input
        id="roster_max"
        name="roster_max"
        type="number"
        class="c-input"
        min="1"
        max="20"
        step="1"
        :value="values.roster_max"
        :aria-describedby="field.describedby"
        :aria-invalid="Boolean(fields.roster_max?.length)"
        @input="number('roster_max', $event)"
        @blur="emit('blur')"
      >
    </ActivityField>
    <ActivityField id="sjtu_only" label="仅限交大" :errors="fields.sjtu_only" v-slot="field">
      <label class="c-check">
        <input
          id="sjtu_only"
          name="sjtu_only"
          type="checkbox"
          :checked="values.sjtu_only"
          :aria-describedby="field.describedby"
          :aria-invalid="Boolean(fields.sjtu_only?.length)"
          @change="check('sjtu_only', $event)"
        >仅限交大
      </label>
    </ActivityField>
    <ActivityField
      id="auto_approve"
      label="报名自动通过"
      :errors="fields.auto_approve"
      :help="hasRegistrations ? '已经有报名了，不能再改「报名自动通过」。' : ''"
      v-slot="field"
    >
      <label class="c-check">
        <input
          id="auto_approve"
          name="auto_approve"
          type="checkbox"
          :checked="values.auto_approve"
          :disabled="disabled || hasRegistrations"
          :aria-describedby="field.describedby"
          :aria-invalid="Boolean(fields.auto_approve?.length)"
          @change="check('auto_approve', $event)"
        >报名自动通过
      </label>
    </ActivityField>
  </fieldset>

  <fieldset class="b-section" :disabled="disabled">
    <legend class="b-section__title">通知</legend>
    <ActivityField
      id="participant_contact"
      label="选手联系方式"
      :errors="fields.participant_contact"
      help="比如选手 QQ 群号。只有报了这项赛事的人看得到，也会写进报名通过、编队和开赛提醒的邮件。不要写进上面公开的详细说明。"
      v-slot="field"
    >
      <textarea
        id="participant_contact"
        name="participant_contact"
        class="c-input"
        rows="3"
        maxlength="100"
        :value="values.participant_contact"
        :aria-describedby="field.describedby"
        :aria-invalid="Boolean(fields.participant_contact?.length)"
        @input="text('participant_contact', $event)"
        @blur="emit('blur')"
      />
    </ActivityField>
  </fieldset>
</template>
