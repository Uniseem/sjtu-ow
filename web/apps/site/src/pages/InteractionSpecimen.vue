<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue"
import { useHead } from "@unhead/vue"
import CField from "@sjtu-ow/ui/CField.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CAutosave from "@sjtu-ow/ui/CAutosave.vue"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import { toast } from "../toasts"
import { useViewer } from "../viewer"

useHead({ title: "交互样张 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })
const dialog = ref<HTMLDialogElement | null>(null)
const viewer = useViewer()
const mixed = ref<HTMLInputElement | null>(null)
const checked = ref(false)
const selected = ref("tank")
const pending = ref(false)
const saved = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined
function simulate(): void {
  pending.value = true
  saved.value = false
  timer = setTimeout(() => { pending.value = false; saved.value = true }, 600)
}
onBeforeUnmount(() => { if (timer) clearTimeout(timer) })
onMounted(() => { if (mixed.value) mixed.value.indeterminate = true })
</script>
<template>
  <main id="main" class="l-container l-container--narrow l-section">
    <h1>交互样张</h1>
    <div class="grid gap-8 mt-8 lg:grid-cols-2">
      <section class="c-panel" data-polish="buttons">
        <h2>按钮</h2>
        <div class="flex flex-wrap gap-3 mt-4">
          <button type="button" class="c-btn c-btn--primary" data-control="primary">主要操作</button>
          <button type="button" class="c-btn c-btn--secondary" data-control="secondary">次要操作</button>
          <button type="button" class="c-btn c-btn--tonal">轻强调</button>
          <button type="button" class="c-btn c-btn--danger">危险操作</button>
          <button type="button" class="c-btn c-btn--quiet c-btn--sm">编辑</button>
          <button type="button" class="c-iconbtn" aria-label="示例设置"><CIcon name="settings" /></button>
          <button type="button" class="c-btn c-btn--primary" disabled data-control="disabled">不可操作</button>
        </div>
      </section>
      <section class="c-panel" data-polish="fields">
        <h2>输入状态</h2>
        <div class="grid gap-4 mt-4">
          <CField label="常规输入" input-id="polish-text"><input id="polish-text" type="text" name="polish-text" placeholder="输入内容" data-control="text"></CField>
          <CField label="只读输入" input-id="polish-readonly"><input id="polish-readonly" type="text" value="可选择复制" readonly data-control="readonly"></CField>
          <CField label="禁用输入" input-id="polish-disabled"><input id="polish-disabled" type="text" value="暂不可编辑" disabled data-control="disabled-input"></CField>
          <CField label="字段错误" input-id="polish-invalid" :errors="['请检查这个值。']"><input id="polish-invalid" type="text" value="错误内容" aria-invalid="true" data-control="invalid"></CField>
          <CField label="选择位置" input-id="polish-select"><select id="polish-select" v-model="selected" data-control="select"><option value="tank">坦克</option><option value="damage">输出</option><option value="support">辅助</option></select></CField>
        </div>
      </section>
      <section class="c-panel" data-polish="choices">
        <h2>选择与筛选</h2>
        <div class="grid gap-3 mt-4">
          <CField label="可切换选择" input-id="polish-check" kind="checkbox"><input id="polish-check" v-model="checked" type="checkbox" data-control="check"></CField>
          <label class="c-check"><input ref="mixed" type="checkbox" data-control="mixed">部分选择</label>
          <label class="c-check"><input type="checkbox" checked disabled>已选择但禁用</label>
          <label class="c-check"><input type="radio" name="polish-role" checked data-control="radio">单选状态</label>
          <div class="c-choices"><label class="c-choice"><input type="checkbox" value="tank">坦克</label><label class="c-choice"><input type="checkbox" value="support" checked>辅助</label></div>
        </div>
      </section>
      <section class="c-panel" data-polish="surfaces">
        <h2>菜单与对话框</h2>
        <div class="flex flex-wrap items-center gap-4 mt-4">
          <details class="c-menu" data-control="menu"><summary>更多操作<CIcon name="chevron-down" /></summary><div class="c-menu__panel"><a href="#polish-feedback">查看反馈</a><a href="#polish-empty">查看空状态</a></div></details>
          <button type="button" class="c-btn c-btn--secondary" data-control="dialog-open" @click="dialog?.showModal()">打开对话框</button>
        </div>
        <dialog ref="dialog" class="b-dialog" aria-labelledby="polish-dialog-title" data-control="dialog">
          <div class="b-dialog__head"><h2 id="polish-dialog-title">确认操作</h2><button type="button" class="c-iconbtn" aria-label="关闭样张对话框" @click="dialog?.close()"><CIcon name="close" /></button></div>
          <div class="b-dialog__body"><CField label="对话框输入" input-id="polish-dialog-input"><input id="polish-dialog-input" type="text"></CField><form method="dialog"><button class="c-btn c-btn--primary">完成</button></form></div>
        </dialog>
      </section>
      <section id="polish-feedback" class="c-panel" data-polish="feedback">
        <h2>状态与反馈</h2>
        <div class="flex flex-wrap gap-3 mt-4"><CStatus kind="ok" label="已通过" /><CStatus kind="warn" label="待审核" /><CStatus kind="info" label="即将开始" /></div>
        <div class="grid gap-4 mt-4">
          <CAutosave bare :state="pending ? 'saving' : saved ? 'saved' : 'idle'" :message="pending ? '正在保存…' : saved ? '已保存' : '尚未修改'" :pending="pending" />
          <div class="c-notice c-notice--error"><CIcon name="alert" /><span>操作失败时保留内容，允许重试。</span></div>
          <div class="flex flex-wrap gap-3"><button type="button" class="c-btn c-btn--secondary" :disabled="pending" :aria-busy="pending" data-control="save" @click="simulate">保存样张</button><button type="button" class="c-btn c-btn--secondary" data-control="toast" @click="toast('操作已完成', 'success')">显示操作反馈</button><button type="button" class="c-btn c-btn--secondary" data-control="flash" @click="viewer.flash = '会话提示样张'">显示会话提示</button></div>
        </div>
      </section>
      <section class="c-panel" data-polish="lists">
        <h2>导航与表格</h2>
        <nav class="c-tabs mt-4" aria-label="样张筛选"><a href="#polish-feedback" aria-current="page">当前项目<span class="c-tabs__count">12</span></a><a href="#polish-empty">其他项目</a></nav>
        <table class="c-table c-table--stack mt-4"><thead><tr><th scope="col">名称</th><th scope="col">状态</th><th scope="col">操作</th></tr></thead><tbody><tr><td data-label="名称">较长名称的组件示例</td><td data-label="状态">已发布</td><td data-label="操作"><button class="c-btn c-btn--quiet c-btn--sm" type="button">编辑</button></td></tr></tbody></table>
      </section>
      <section id="polish-empty" data-polish="empty"><CEmpty title="暂无内容" action-url="#polish-feedback" action-label="返回反馈" /></section>
    </div>
  </main>
</template>
