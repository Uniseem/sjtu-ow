import { computed, onBeforeUnmount, onMounted, shallowRef } from "vue"
import { onBeforeRouteLeave } from "vue-router"
import { ApiError, postApiAdminImagesUpload, type Requester, type PostApiAdminImagesUploadIn } from "@sjtu-ow/api"
import type { Image } from "./types"

export type UploadState = "queued" | "reading" | "uploading" | "saved" | "failed" | "uncertain"
export type UploadItem = {
  key: string
  file: File
  title: string
  collectionKey: string
  state: UploadState
  message: string
  image: Image | null
  body: PostApiAdminImagesUploadIn | null
  retryAt: number | null
}

const LIMIT = 5 * 1024 * 1024
const TYPES = new Set(["image/jpeg", "image/png", "image/webp"])

function readFile(file: File, signal: AbortSignal): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    const abort = () => reader.abort()
    signal.addEventListener("abort", abort, { once: true })
    reader.onload = () => {
      signal.removeEventListener("abort", abort)
      if (typeof reader.result === "string") resolve(reader.result)
      else reject(new Error("无法读取图片。"))
    }
    reader.onerror = () => {
      signal.removeEventListener("abort", abort)
      reject(new Error("无法读取图片。"))
    }
    reader.onabort = () => {
      signal.removeEventListener("abort", abort)
      reject(new DOMException("读取已取消。", "AbortError"))
    }
    reader.readAsDataURL(file)
  })
}

export function useUploadQueue(api: Requester, saved?: (image: Image) => void) {
  const items = shallowRef<UploadItem[]>([])
  const pending = shallowRef(false)
  const message = shallowRef("")
  const uncertain = computed(() => items.value.some((item) => item.state === "uncertain"))
  const complete = computed(() => items.value.filter((item) => item.state === "saved").length)
  let controller: AbortController | null = null
  let disposed = false
  let running: Promise<void> | null = null

  function patch(key: string, value: Partial<UploadItem>): void {
    items.value = items.value.map((item) => item.key === key ? { ...item, ...value } : item)
  }

  function add(files: File[], collectionKey: string): void {
    message.value = ""
    if (pending.value || uncertain.value) {
      message.value = "请先完成或重试当前上传。"
      return
    }
    const rows: UploadItem[] = []
    for (const file of files) {
      const invalidType = !TYPES.has(file.type) && !/\.(jpe?g|png|webp)$/i.test(file.name)
      const invalidSize = file.size <= 0 || file.size > LIMIT
      rows.push({
        key: crypto.randomUUID(),
        file,
        title: file.name.replace(/\.[^.]+$/, ""),
        collectionKey,
        state: invalidType || invalidSize ? "failed" : "queued",
        message: invalidType ? "请选择 JPG、PNG 或 WebP 图片。"
          : invalidSize ? "每张图片不超过 5 MB，不能上传空文件。" : "",
        image: null,
        body: null,
        retryAt: null,
      })
    }
    items.value = [...items.value, ...rows]
  }

  function rename(key: string, title: string): void {
    const item = items.value.find((row) => row.key === key)
    if (!item || item.body || item.state !== "queued") return
    patch(key, { title })
  }

  function configure(collectionKey: string): void {
    if (pending.value || uncertain.value) return
    items.value = items.value.map((item) => item.state === "queued" && !item.body ? { ...item, collectionKey } : item)
  }

  function remove(key: string): void {
    const item = items.value.find((row) => row.key === key)
    if (!item || pending.value || item.state === "uncertain" || item.state === "saved") return
    items.value = items.value.filter((row) => row.key !== key)
  }

  async function uploadItem(item: UploadItem): Promise<boolean> {
    if (disposed || !controller) return false
    if (item.retryAt && Date.now() < item.retryAt) {
      message.value = "上传太频繁，请稍后重试。"
      return false
    }
    try {
      let body = item.body
      if (!body) {
        patch(item.key, { state: "reading", message: "正在读取…" })
        const dataURL = await readFile(item.file, controller.signal)
        if (disposed) return false
        body = {
          title: item.title.trim() || item.file.name,
          collection_key: item.collectionKey,
          file_name: item.file.name,
          data_url: dataURL,
        }
        patch(item.key, { body })
      }
      patch(item.key, { state: "uploading", message: "正在上传…" })
      const result = await postApiAdminImagesUpload(api, body, {
        key: item.key,
        signal: controller.signal,
        unauthorized: "throw",
      })
      if (disposed) return false
      if (!result.image || !Number.isSafeInteger(result.image.id) || result.image.id <= 0) {
        throw new ApiError(0, "invalid_receipt", "上传回执无效，请重试上次上传。")
      }
      patch(item.key, { state: "saved", message: "已上传", image: result.image, body: null, retryAt: null })
      saved?.(result.image)
      return true
    } catch (cause) {
      if (disposed) return false
      const error = cause instanceof ApiError ? cause : null
      const retryable = error === null || error.status === 0 || error.status === 429 || error.status >= 500
      patch(item.key, {
        state: retryable ? "uncertain" : "failed",
        message: error?.message ?? "暂时无法上传，请重试上次上传。",
        retryAt: error?.status === 429 ? Date.now() + (error.retryAfter ?? 5) * 1000 : null,
      })
      return false
    }
  }

  async function run(retryOnly: boolean): Promise<void> {
    controller = new AbortController()
    pending.value = true
    message.value = ""
    try {
      const selected = items.value.filter((item) => retryOnly ? item.state === "uncertain" : item.state === "queued")
      // Sequential writes keep retry identity and completion ordering unambiguous.
      for (const item of selected) {
        if (!await uploadItem(item)) break
      }
    } finally {
      if (!disposed) pending.value = false
    }
  }

  function start(retryOnly = false): Promise<void> {
    if (running) return running
    if (!retryOnly && uncertain.value) {
      message.value = "上次上传尚未确认，请先重试。"
      return Promise.resolve()
    }
    const task = run(retryOnly)
    running = task
    void task.finally(() => { if (running === task) running = null })
    return task
  }

  function preventUnload(event: BeforeUnloadEvent): void {
    if (!pending.value && !uncertain.value) return
    event.preventDefault()
    event.returnValue = ""
  }
  onBeforeRouteLeave(() => {
    if (!pending.value && !uncertain.value) return true
    message.value = "图片上传尚未确认，请先完成或重试当前上传。"
    return false
  })
  onMounted(() => { window.addEventListener("beforeunload", preventUnload) })
  onBeforeUnmount(() => {
    disposed = true
    controller?.abort()
    window.removeEventListener("beforeunload", preventUnload)
  })
  return { items, pending, message, uncertain, complete, add, rename, remove, configure, start, retry: () => start(true) }
}
