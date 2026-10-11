<script setup lang="ts">
defineEmits<{ close: [] }>()
</script>
<template>
  <section class="b-section" aria-label="Markdown 写法">
    <div class="c-panel__head">
      <h2 class="b-section__title">Markdown 写法</h2>
      <button type="button" class="c-btn c-btn--quiet c-btn--sm" @click="$emit('close')">收起</button>
    </div>
    <table class="c-table c-table--stack">
      <thead><tr><th>想写什么</th><th>怎么写</th></tr></thead>
      <tbody>
        <tr><td>标题</td><td><code>## 二级标题</code>，标题独占一行</td></tr>
        <tr><td>加粗</td><td><code>**加粗文字**</code></td></tr>
        <tr><td>斜体</td><td><code>*斜体文字*</code></td></tr>
        <tr><td>删除线</td><td><code>~~删除文字~~</code></td></tr>
        <tr><td>列表</td><td>每行以 <code>- </code> 或 <code>1. </code> 开头</td></tr>
        <tr><td>引用</td><td>每行以 <code>&gt; </code> 开头</td></tr>
        <tr><td>链接</td><td><code>[链接文字](https://example.com)</code></td></tr>
        <tr><td>图片</td><td><code>![图注](图片地址)</code>，单独放一行</td></tr>
        <tr><td>代码</td><td>行内代码用一对反引号，多行代码用三对反引号</td></tr>
        <tr><td>B 站视频</td><td>把完整视频链接单独放一行</td></tr>
      </tbody>
    </table>
    <p class="c-field__help">按 Tab 缩进，Shift+Tab 减少缩进。工具栏支持键盘操作。写完先预览，再发布。</p>
  </section>
</template>
