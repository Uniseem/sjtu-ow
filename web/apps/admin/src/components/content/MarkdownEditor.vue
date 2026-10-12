<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"
import type { EditorView } from "@codemirror/view"
import { ApiError, getApiAdminImageCollections } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminSession } from "../../core/session"
import { useUploadQueue } from "../../pages/content/use-upload-queue"
import UploadRows from "./UploadRows.vue"
import { imageUrl } from "@sjtu-ow/shared/media"
import ImagePicker from "./ImagePicker.vue"
import MarkdownHelp from "./MarkdownHelp.vue"
import MarkdownPreview from "./MarkdownPreview.vue"
import { commandEdit, insertImage, insertVideo, toolbarCommands, type MarkdownCommand } from "./markdown-commands"
import type { Collection, Image } from "../../pages/content/types"

const props = withDefaults(defineProps<{
  modelValue: string
  id?: string
  name?: string
  label?: string
  disabled?: boolean
  describedby?: string
  invalid?: boolean
  previewUrl?: string | null
}>(), {
  id: "body_md",
  name: "body",
  label: "正文",
  disabled: false,
  invalid: false,
  previewUrl: null,
})
const emit = defineEmits<{ "update:modelValue": [value: string]; blur: [] }>()
const api = useAdminApi()
const { user } = useAdminSession()
const collections = ref<Collection[]>([])
const uploadCollection = ref("")
const uploadMessage = ref("")
const canUpload = computed(() => Boolean(user.value?.superuser || user.value?.caps.includes("images.contribute")))
const uploads = useUploadQueue(api, (image) => selected(image))
const host = ref<HTMLDivElement | null>(null)
const fallback = ref<HTMLTextAreaElement | null>(null)
const editorReady = ref(false)
const loadError = ref("")
const help = ref(false)
const picker = ref(false)
const preview = ref(false)
const sideBySide = ref(false)
const fullscreen = ref(false)
const container = ref<HTMLDivElement | null>(null)
let fullscreenFocus: HTMLElement | null = null
const wordCount = computed(() => [...props.modelValue.replace(/\s/g, "")].length)
let view: EditorView | null = null
let destroyed = false
let changingFromProp = false
let previousFocus: HTMLElement | null = null
let selectedRange: { from: number; to: number } | null = null

function selection() {
  if (view) {
    const main = view.state.selection.main
    return { text: view.state.doc.toString(), from: main.from, to: main.to }
  }
  return {
    text: props.modelValue,
    from: fallback.value?.selectionStart ?? props.modelValue.length,
    to: fallback.value?.selectionEnd ?? props.modelValue.length,
  }
}

function apply(edit: ReturnType<typeof commandEdit>): void {
  if (props.disabled) return
  if (view) {
    view.dispatch({
      changes: { from: edit.from, to: edit.to, insert: edit.insert },
      selection: { anchor: edit.anchor, head: edit.head ?? edit.anchor },
      scrollIntoView: true,
    })
    view.focus()
    return
  }
  const text = props.modelValue.slice(0, edit.from) + edit.insert + props.modelValue.slice(edit.to)
  emit("update:modelValue", text)
  void nextTick(() => {
    fallback.value?.focus()
    fallback.value?.setSelectionRange(edit.anchor, edit.head ?? edit.anchor)
  })
}

function run(command: MarkdownCommand): void {
  apply(commandEdit(command, selection()))
}

function video(): void {
  if (props.disabled) return
  const current = selection()
  const edit = insertVideo(current, window.prompt("粘贴 B 站视频链接（bilibili.com/video/… 或 b23.tv/…）："))
  if (edit) apply(edit)
}
function togglePreview(): void {
  preview.value = !preview.value
  sideBySide.value = false
  if (!preview.value) void nextTick(() => { view ? view.focus() : fallback.value?.focus() })
}
function toggleSideBySide(): void {
  sideBySide.value = !sideBySide.value
  preview.value = false
  void nextTick(() => { view?.requestMeasure(); view ? view.focus() : fallback.value?.focus() })
}
function toggleFullscreen(): void {
  if (!fullscreen.value) {
    fullscreenFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    fullscreen.value = true
  } else {
    fullscreen.value = false
  }
  void nextTick(() => {
    view?.requestMeasure()
    document.documentElement.classList.toggle("has-fullscreen-markdown-editor", Boolean(document.querySelector(".markdown-editor.is-fullscreen")))
    if (fullscreen.value) { view ? view.focus() : fallback.value?.focus() }
    else { fullscreenFocus?.focus(); fullscreenFocus = null }
  })
}
function fullscreenKey(event: KeyboardEvent): void {
  if (!fullscreen.value || !container.value || event.defaultPrevented || picker.value) return
  if (event.key === "Escape") { event.preventDefault(); toggleFullscreen(); return }
  if (event.key !== "Tab") return
  const controls: HTMLElement[] = []
  // Include the editable node inside the open shadow root in document order.
  for (const node of container.value.querySelectorAll<HTMLElement>("button,a[href],input,select,textarea,iframe,[tabindex],.markdown-editor__host")) {
    if (node === host.value && view?.contentDOM) controls.push(view.contentDOM)
    else if (!node.hasAttribute("disabled") && node.tabIndex >= 0 && node.getClientRects().length) controls.push(node)
  }
  const available = controls.filter(node => node.getClientRects().length)
  const first = available[0], last = available.at(-1)
  const originDocument = event.view?.document
  if (originDocument && originDocument !== document) {
    const frameControls = [...originDocument.querySelectorAll<HTMLElement>("a[href],button,input,select,textarea,[tabindex]")].filter(node => !node.hasAttribute("disabled") && node.tabIndex >= 0 && node.getClientRects().length)
    const active = originDocument.activeElement
    if (!event.shiftKey && (!frameControls.length || active === frameControls.at(-1)) && document.activeElement === last && first) { event.preventDefault(); first.focus() }
    else if (event.shiftKey && (!frameControls.length || active === frameControls[0]) && document.activeElement === first && last) { event.preventDefault(); last.focus() }
    return
  }
  const active = host.value?.shadowRoot?.activeElement ?? document.activeElement
  if (event.shiftKey && active === first && last) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && active === last && first) { event.preventDefault(); first.focus() }
}

function chooseImage(): void {
  if (props.disabled) return
  previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  selectedRange = { from: selection().from, to: selection().to }
  picker.value = true
}

function selected(image: Image): void {
  const current = selection()
  if (selectedRange) {
    current.from = Math.min(selectedRange.from, current.text.length)
    current.to = Math.min(selectedRange.to, current.text.length)
  }
  apply(insertImage(current, imageUrl(image.id, "max-1600x1600"), image.title))
  picker.value = false
  selectedRange = null
}

function closePicker(): void {
  picker.value = false
  selectedRange = null
  void nextTick(() => { previousFocus?.focus(); previousFocus = null })
}

function fallbackKey(event: KeyboardEvent): void {
  if (props.disabled || (!event.metaKey && !event.ctrlKey)) return
  const command = event.key.toLowerCase() === "b" ? "bold"
    : event.key.toLowerCase() === "i" ? "italic"
    : event.key.toLowerCase() === "k" ? "link" : null
  if (!command) return
  event.preventDefault()
  run(command)
}

function fallbackInput(event: Event): void {
  if (event.target instanceof HTMLTextAreaElement) emit("update:modelValue", event.target.value)
}

function filesFromEvent(event: ClipboardEvent | DragEvent): File[] {
  const data = "clipboardData" in event ? event.clipboardData : event.dataTransfer
  return [...(data?.files ?? [])].filter((file) => file.type.startsWith("image/"))
}

function pasted(event: ClipboardEvent): void {
  const files = filesFromEvent(event)
  if (props.disabled || files.length === 0) return
  event.preventDefault()
  uploadFiles(files)
}

function dropped(event: DragEvent): void {
  const files = filesFromEvent(event)
  if (props.disabled || files.length === 0) return
  event.preventDefault()
  uploadFiles(files)
}

function uploadFiles(files: File[]): void {
  if (!canUpload.value) { uploadMessage.value = "你没有上传图片的权限。"; return }
  uploadMessage.value = ""
  uploads.add(files, uploadCollection.value)
  if (uploadCollection.value) void uploads.start()
}
async function loadCollections(): Promise<void> {
  if (!canUpload.value) return
  try {
    const result = await getApiAdminImageCollections(api)
    if (destroyed) return
    collections.value = result.collections.filter(item => item.can_upload)
    uploadCollection.value = collections.value[0]?.key ?? ""
    uploads.configure(uploadCollection.value)
  } catch (cause) {
    if (!destroyed) uploadMessage.value = cause instanceof ApiError ? cause.message : "图片集合暂时无法加载。"
  }
}
async function initialize(): Promise<void> {
  loadError.value = ""
  try {
    const [{ EditorState, Compartment }, { EditorView: View, keymap, drawSelection, highlightActiveLine },
      { defaultKeymap, history, historyKeymap, indentWithTab }, { markdown },
      { syntaxHighlighting, defaultHighlightStyle, bracketMatching, indentOnInput }] = await Promise.all([
      import("@codemirror/state"),
      import("@codemirror/view"),
      import("@codemirror/commands"),
      import("@codemirror/lang-markdown"),
      import("@codemirror/language"),
    ])
    if (destroyed || !host.value) return
    if (!("adoptedStyleSheets" in ShadowRoot.prototype)) {
      loadError.value = "浏览器暂不支持编辑器，已切换到文本框。"
      return
    }
    const shadow = host.value.shadowRoot ?? host.value.attachShadow({ mode: "open" })
    const editable = new Compartment()
    const attributes = new Compartment()
    const theme = View.theme({
      "&": { color: "var(--color-fg)", backgroundColor: "var(--color-surface)", minHeight: "24rem" },
      ".cm-content": { fontFamily: "var(--font-mono)", padding: "1rem", caretColor: "var(--color-fg)" },
      ".cm-scroller": { overflow: "auto", lineHeight: "1.7" },
      ".cm-gutters": { backgroundColor: "var(--color-surface)", borderColor: "var(--color-line)" },
      ".cm-activeLine": { backgroundColor: "var(--color-surface-2)" },
      "&.cm-focused": { outline: "2px solid var(--color-primary)", outlineOffset: "2px" },
      ".cm-selectionBackground, &.cm-focused .cm-selectionBackground": { backgroundColor: "var(--color-primary-soft)" },
    })
    view = new View({
      root: shadow,
      parent: shadow,
      state: EditorState.create({
        doc: props.modelValue,
        extensions: [
          editable.of(View.editable.of(!props.disabled)),
          attributes.of(View.contentAttributes.of({
            "aria-label": props.label,
            "aria-multiline": "true",
            "aria-invalid": String(props.invalid),
            ...(props.describedby ? { "aria-describedby": props.describedby } : {}),
            id: `${props.id}-editor`,
          })),
          markdown(),
          history(),
          drawSelection(),
          highlightActiveLine(),
          bracketMatching(),
          indentOnInput(),
          syntaxHighlighting(defaultHighlightStyle),
          theme,
          View.lineWrapping,
          keymap.of([
            { key: "Mod-b", run: () => { run("bold"); return true } },
            { key: "Mod-i", run: () => { run("italic"); return true } },
            { key: "Mod-k", run: () => { run("link"); return true } },
            ...defaultKeymap,
            ...historyKeymap,
            indentWithTab,
          ]),
          View.updateListener.of((update) => {
            if (update.docChanged && !changingFromProp) {
              const source = update.state.doc.toString()
              if (fallback.value) fallback.value.value = source
              emit("update:modelValue", source)
            }
          }),
          View.domEventHandlers({
            blur: () => { emit("blur"); return false },
            paste: (event) => { pasted(event); return event.defaultPrevented },
            drop: (event) => { dropped(event); return event.defaultPrevented },
          }),
        ],
      }),
    })
    editorReady.value = true
    void nextTick(() => { view?.requestMeasure() })
    watch(() => props.disabled, (disabled) => {
      view?.dispatch({ effects: editable.reconfigure(View.editable.of(!disabled)) })
    })
    watch(() => [props.invalid, props.describedby], () => {
      view?.dispatch({ effects: attributes.reconfigure(View.contentAttributes.of({
        "aria-label": props.label,
        "aria-multiline": "true",
        "aria-invalid": String(props.invalid),
        ...(props.describedby ? { "aria-describedby": props.describedby } : {}),
      })) })
    })
  } catch (error) {
    if (destroyed) return
    loadError.value = "编辑器暂时无法加载，已切换到文本框。"
    // A failed editor import never prevents writing or storing a draft.
    if (error instanceof Error) console.warn("Markdown editor unavailable:", error.message)
  }
}

watch(() => props.modelValue, (text) => {
  if (fallback.value) fallback.value.value = text
  if (!view || view.state.doc.toString() === text) return
  changingFromProp = true
  try {
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } })
  } finally {
    changingFromProp = false
  }
})
onMounted(() => { void initialize(); void loadCollections(); document.addEventListener("keydown", fullscreenKey) })
onBeforeUnmount(() => {
  destroyed = true
  document.removeEventListener("keydown", fullscreenKey)
  if (fullscreen.value && document.querySelectorAll(".markdown-editor.is-fullscreen").length <= 1) document.documentElement.classList.remove("has-fullscreen-markdown-editor")
  view?.destroy(); view = null
})
defineExpose({ insertImage: selected, focus: () => { view ? view.focus() : fallback.value?.focus() } })
</script>
<template>
  <div ref="container" class="c-field markdown-editor" :class="{ 'is-fullscreen': fullscreen }" data-markdown-editor :data-markdown-field="name">
    <div class="b-rowacts" role="toolbar" :aria-label="`${label}工具栏`">
      <button v-for="item in toolbarCommands" :key="item.command" :data-markdown-command="item.command" type="button" class="c-btn c-btn--quiet c-btn--sm" :title="item.shortcut ? `${item.label}（${item.shortcut}）` : item.label" :disabled="disabled" @click="run(item.command)">{{ item.label }}</button>
      <button type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="disabled" data-markdown-command="image-upload" @click="chooseImage">插入图片</button>
      <button type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="disabled" data-markdown-command="video" @click="video">B 站视频</button>
      <button type="button" class="c-btn c-btn--quiet c-btn--sm" :aria-pressed="preview" data-markdown-command="preview" @click="togglePreview">预览</button>
      <button type="button" class="c-btn c-btn--quiet c-btn--sm markdown-editor__desktop-action" :aria-pressed="sideBySide" data-markdown-command="side-by-side" @click="toggleSideBySide">并排预览</button>
      <button type="button" class="c-btn c-btn--quiet c-btn--sm markdown-editor__desktop-action" :aria-pressed="fullscreen" data-markdown-command="fullscreen" @click="toggleFullscreen">{{ fullscreen ? '退出全屏' : '全屏' }}</button>
      <button type="button" class="c-btn c-btn--quiet c-btn--sm" :aria-expanded="help" @click="help = !help">写法</button>
    </div>
    <p v-if="loadError" class="c-field__help" role="status">{{ loadError }}</p>
    <div class="markdown-editor__panes" :class="{ 'is-side-by-side': sideBySide }">
      <div class="markdown-editor__source" :hidden="preview && !sideBySide">
        <div :hidden="!editorReady" ref="host" class="c-input markdown-editor__host" :aria-hidden="!editorReady" />
        <textarea :hidden="editorReady" data-markdown-source :id="id" ref="fallback" class="c-input" :name="name" :value="modelValue" :disabled="disabled" :aria-label="label" :aria-describedby="describedby" :aria-invalid="invalid" rows="18" @input="fallbackInput" @keydown="fallbackKey" @paste="pasted" @drop="dropped" @blur="$emit('blur')" />
      </div>
      <MarkdownPreview :body="modelValue" :open="preview || sideBySide" @frame-keydown="fullscreenKey" />
    </div>
    <p class="c-field__help">{{ wordCount }} 字。图片可粘贴或拖入，上传后才会插入正文。</p>
    <section v-if="uploads.items.value.length || uploadMessage" class="b-section" aria-label="正文图片上传">
      <h2 class="b-section__title">上传正文图片</h2>
      <p v-if="uploadMessage" class="c-notice c-notice--error" role="alert">{{ uploadMessage }}</p>
      <label class="c-field__label" :for="`${id}-upload-collection`">放进集合</label>
      <select :id="`${id}-upload-collection`" v-model="uploadCollection" class="c-input" :disabled="uploads.pending.value || uploads.uncertain.value" @change="uploads.configure(uploadCollection)">
        <option value="" disabled>选择集合</option>
        <option v-for="item in collections" :key="item.id" :value="item.key">{{ item.name }}</option>
      </select>
      <UploadRows :items="uploads.items.value" :pending="uploads.pending.value" @rename="uploads.rename" @remove="uploads.remove" />
      <p v-if="uploads.message.value" role="alert">{{ uploads.message.value }}</p>
      <div class="b-actions">
        <button v-if="uploads.uncertain.value" type="button" class="c-btn c-btn--secondary" :disabled="uploads.pending.value" @click="uploads.retry">重试上次上传</button>
        <button v-else type="button" class="c-btn c-btn--secondary" :disabled="!uploadCollection || uploads.pending.value" @click="uploads.start()">上传图片</button>
        <button v-if="!collections.length" type="button" class="c-btn c-btn--quiet" :disabled="uploads.pending.value" @click="loadCollections">重新加载集合</button>
      </div>
    </section>
    <MarkdownHelp v-if="help" @close="help = false" />
    <ImagePicker v-if="picker" @select="selected" @close="closePicker" />
  </div>
</template>

<style scoped>
.markdown-editor__panes { min-width: 0; }
.markdown-editor__source { min-width: 0; }
.markdown-editor__source[hidden], .markdown-editor__source [hidden] { display: none; }
.markdown-editor__desktop-action { display: none; }
.markdown-editor.is-fullscreen {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  flex-direction: column;
  overflow: auto;
  margin: 0;
  padding: 1rem;
  background: var(--color-surface);
}
.markdown-editor.is-fullscreen .markdown-editor__panes { flex: 1; }
:global(html.has-fullscreen-markdown-editor) { overflow: hidden; }
@media (min-width: 769px) {
  .markdown-editor__desktop-action { display: inline-flex; }
  .markdown-editor__panes.is-side-by-side {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 1rem;
  }
}
</style>
