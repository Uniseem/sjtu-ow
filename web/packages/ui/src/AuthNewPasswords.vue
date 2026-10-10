<script setup lang="ts">
import CField from "./CField.vue"
withDefaults(defineProps<{ fresh?: boolean; errors?: Record<string, string[]> }>(), { errors: () => ({}) })
const password = defineModel<string>("password", { default: "" })
const confirmation = defineModel<string>("confirmation", { default: "" })
</script>
<template>
  <CField :label="fresh ? '密码' : '新密码'" input-id="id_password1" required :errors="errors.password">
    <input id="id_password1" v-model="password" type="password" name="password1" :placeholder="fresh ? '密码' : '新密码'" autocomplete="new-password" required aria-describedby="id_password1_helptext">
    <template #help><ul id="id_password1_helptext"><li>你的密码不能与你的其他个人信息太相似。</li><li>你的密码必须包含至少 8 个字符。</li><li>你的密码不能是一个常见密码。</li><li>你的密码不能全都是数字。</li></ul></template>
  </CField>
  <CField :label="fresh ? '确认密码' : '确认新密码'" input-id="id_password2" required :errors="errors.confirm_password">
    <input id="id_password2" v-model="confirmation" type="password" name="password2" :placeholder="fresh ? '确认密码' : '确认新密码'" autocomplete="new-password" required>
  </CField>
</template>
