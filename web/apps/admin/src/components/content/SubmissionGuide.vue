<script setup lang="ts">
import CIcon from "@sjtu-ow/ui/CIcon.vue"
</script>
<template>
  <div class="c-notice c-notice--info" data-submission-guide>
    <CIcon name="info" />
    <div class="c-notice__body">
      <ul class="list-disc pl-5">
        <li>填好标题、选分类，摘要写一两句，会显示在文章列表和分享卡片上。</li>
        <li>正文用 Markdown 写，工具栏有加粗、标题、列表、链接这些按钮，点「写法」看写法。图片点图片按钮、拖进来或直接粘贴就会上传，单独一行的图片方括号里写图注；B 站视频把链接单独贴一行。点「预览」看排出来的样子。</li>
        <li>写的时候自动存成草稿（表单上方写着「已保存」），以后在后台首页「我的文章」里接着写。</li>
        <li>写完点底部的「发布」就上线了，不用等审核。改已发布的文章，改完再点一次「发布」。</li>
      </ul>
    </div>
  </div>
</template>
