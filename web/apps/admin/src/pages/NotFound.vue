<script setup lang="ts">
import { computed } from "vue"
import { useRoute } from "vue-router"
import AdminError from "../components/AdminError.vue"
const route=useRoute()
const failure=computed(()=>route.path==="/admin/forbidden/" ? {status:403,title:"没有权限",message:"你没有权限进入管理后台。",retry:false} : {status:404,title:"页面不存在",message:"请从后台导航找到需要的页面。",retry:false})
</script>
<template><AdminError :failure="failure" login-href="/accounts/login/?next=%2Fadmin%2F" /></template>
