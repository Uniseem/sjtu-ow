import { ApiError } from "@sjtu-ow/api"
import { inspectAvatar } from "./image-inspect"

const IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"])

/** Browser-only conversion for the generated avatar JSON upload contract. */
export async function avatarDataURL(file: File, signal?: AbortSignal): Promise<string> {
  if (!IMAGE_TYPES.has(file.type)) {
    return Promise.reject(new ApiError(422, "invalid_image", "请选择 JPG、PNG 或 WebP 图片。"))
  }
  if (file.size === 0) {
    return Promise.reject(new ApiError(422, "empty_image", "图片是空的，请重新选择。"))
  }
  if (file.size > 5 * 1024 * 1024) {
    return Promise.reject(new ApiError(413, "image_too_large", "图片不能超过 5 MB。"))
  }
  await inspectAvatar(file, signal)
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    function cleanup(): void {
      signal?.removeEventListener("abort", abort)
      reader.onload = null
      reader.onerror = null
      reader.onabort = null
    }
    function abort(): void {
      reader.abort()
      cleanup()
      reject(new DOMException("Upload cancelled", "AbortError"))
    }
    reader.onload = () => {
      const result = reader.result
      cleanup()
      if (typeof result !== "string" || !result.startsWith("data:image/")) {
        reject(new ApiError(422, "invalid_image", "无法读取这张图片。"))
        return
      }
      resolve(result)
    }
    reader.onerror = () => {
      cleanup()
      reject(new ApiError(0, "file_read_failed", "无法读取这张图片，请重新选择。"))
    }
    reader.onabort = () => {
      cleanup()
      reject(new DOMException("Upload cancelled", "AbortError"))
    }
    if (signal?.aborted) {
      abort()
      return
    }
    signal?.addEventListener("abort", abort, { once: true })
    reader.readAsDataURL(file)
  })
}

/** Generated JSON exports are downloaded without leaking them into URLs. */
export function downloadJSON(value: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(value, null, 2) + "\n"], { type: "application/json;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  anchor.hidden = true
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 30_000)
}
