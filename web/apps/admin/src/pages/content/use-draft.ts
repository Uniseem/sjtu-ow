import { computed, ref, watch } from "vue"
import { ApiError, type CallExtras } from "@sjtu-ow/api"
import type { SaveReceipt, SaveRequest } from "@sjtu-ow/shared/autosave"
import { useAdminSave } from "../../core/use-save"
import { useAdminAction } from "../../core/use-action"
import { readContentCurrent } from "./save-values"
import { contentPreviewURL } from "./preview-url"

export type DraftOptions<T extends object> = {
  initial: T
  version: number
  unpublished: boolean
  available: () => boolean
  transport: (body: SaveRequest<T>, extras: CallExtras) => Promise<SaveReceipt<T>>
  publish: (version: number, extras: CallExtras) => Promise<{ version: number }>
  refresh: () => Promise<{ version: number; draft: T; preview_url: string | null; has_unpublished_changes?: boolean }>
  preview_url?: string | null
  previewRoute?: string
  readCurrent?: (value: unknown) => { version: number; values: T } | null
}

/** Ordinary pages, pins and introduction share save/publish ordering. */
export function useContentDraft<T extends object>(options: DraftOptions<T>) {
  const notice = ref("")
  const confirmation = ref(false)
  const unpublished = ref(options.unpublished)
  const publishing = ref(false)
  const previewURL = ref(contentPreviewURL(options.preview_url))
  const save = useAdminSave<T>({
    initial: options.initial,
    version: options.version,
    available: () => options.available() && !publishing.value,
    readCurrent: options.readCurrent ?? ((value) => readContentCurrent(value, options.initial)),
    transport: async (body, key, signal) => {
      const result = await options.transport(body, { key, signal, unauthorized: "throw" })
      if (result.saved.length) unpublished.value = true
      return result
    },
  })
  const publication = useAdminAction(
    (version: number, extras) => options.publish(version, extras),
    async (result) => {
      if (!Number.isSafeInteger(result.version) || result.version < 0) throw new ApiError(0, "invalid_receipt", "发布回执无效，请重试。")
      unpublished.value = false
      confirmation.value = false
      notice.value = "已发布，网站上的内容已更新。"
      // Publishing increments the same object's version. Keep autosave aligned.
      if (!save.controller.reset(save.values.value, result.version)) {
        notice.value = "已发布，尚有新的草稿改动待保存。"
        unpublished.value = true
      }
    },
  )

  const blocked = computed(() => publication.pending.value || publication.uncertain.value)
  watch(blocked, (value) => { publishing.value = value }, { flush: "sync" })

  async function prepare(): Promise<void> {
    if (!options.available() || publishing.value || !await save.flush()) return
    confirmation.value = true
  }
  async function publish(): Promise<void> {
    if (!options.available() || publishing.value || !await save.flush()) return
    await publication.submit(save.snapshot.value.version)
  }
  async function openPreview(): Promise<void> {
    if (!options.available()) return
    // Open synchronously so browser popup policies do not reject a saved preview.
    const target = window.open("about:blank", "_blank")
    if (target) target.opener = null
    if (!await save.flush()) { target?.close(); return }
    try {
      const current = await options.refresh()
      previewURL.value = options.previewRoute ?? contentPreviewURL(current.preview_url)
      if (!previewURL.value) {
        target?.close()
        notice.value = "预览暂时不可用，请稍后再试。"
        return
      }
      if (target) target.location.replace(previewURL.value)
      else notice.value = "浏览器拦住了预览窗口，请允许弹窗后重试。"
    } catch (cause) {
      target?.close()
      notice.value = cause instanceof ApiError ? cause.message : "暂时无法预览，请稍后再试。"
    }
  }
  return { save, publication, blocked, notice, confirmation, unpublished, previewURL, prepare, publish, openPreview }
}
