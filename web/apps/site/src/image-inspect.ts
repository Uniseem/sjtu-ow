import { ApiError } from "@sjtu-ow/api"

export type ImageDimensions = { width: number; height: number }
const MAX_PIXELS = 40_000_000
const MIN_SIDE = 128

function invalid(message = "无法读取这张图片，请重新选择。"): never {
  throw new ApiError(422, "invalid_image", message)
}

function dimensions(width: number, height: number): ImageDimensions {
  if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height) || width <= 0 || height <= 0) invalid()
  if (width < MIN_SIDE || height < MIN_SIDE) invalid("图片至少需要 128 × 128 像素。")
  if (width * height > MAX_PIXELS) invalid("图片不能超过 4000 万像素。")
  return { width, height }
}

function byteString(bytes: Uint8Array, offset: number, length: number): string {
  if (offset + length > bytes.length) return ""
  return String.fromCharCode(...bytes.subarray(offset, offset + length))
}

function png(bytes: Uint8Array): ImageDimensions {
  const signature = [137, 80, 78, 71, 13, 10, 26, 10]
  if (bytes.length < 33 || !signature.every((byte, index) => bytes[index] === byte)) invalid()
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  if (view.getUint32(8) !== 13 || byteString(bytes, 12, 4) !== "IHDR") invalid()
  return dimensions(view.getUint32(16), view.getUint32(20))
}

function jpeg(bytes: Uint8Array): ImageDimensions {
  if (bytes.length < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8) invalid()
  let offset = 2
  const frames = new Set([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf])
  while (offset < bytes.length) {
    if (bytes[offset] !== 0xff) invalid()
    while (offset < bytes.length && bytes[offset] === 0xff) offset += 1
    if (offset >= bytes.length) invalid()
    const marker = bytes[offset++]
    if (marker === 0xd9 || marker === 0xda) break
    // Standalone markers carry no length.
    if (marker === 0x01 || marker >= 0xd0 && marker <= 0xd7) continue
    if (offset + 2 > bytes.length) invalid()
    const length = bytes[offset] * 256 + bytes[offset + 1]
    if (length < 2 || offset + length > bytes.length) invalid()
    if (frames.has(marker)) {
      if (length < 8) invalid()
      const height = bytes[offset + 3] * 256 + bytes[offset + 4]
      const width = bytes[offset + 5] * 256 + bytes[offset + 6]
      return dimensions(width, height)
    }
    offset += length
  }
  return invalid()
}

function uint24(bytes: Uint8Array, offset: number): number {
  if (offset + 3 > bytes.length) invalid()
  return bytes[offset] + bytes[offset + 1] * 256 + bytes[offset + 2] * 65536
}

function webp(bytes: Uint8Array): ImageDimensions {
  if (bytes.length < 20 || byteString(bytes, 0, 4) !== "RIFF" || byteString(bytes, 8, 4) !== "WEBP") invalid()
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const end = view.getUint32(4, true) + 8
  if (end > bytes.length || end < 20) invalid()
  let offset = 12
  while (offset + 8 <= end) {
    const kind = byteString(bytes, offset, 4)
    const length = view.getUint32(offset + 4, true)
    const body = offset + 8
    if (body + length > end) invalid()
    if (kind === "VP8X") {
      if (length < 10) invalid()
      return dimensions(uint24(bytes, body + 4) + 1, uint24(bytes, body + 7) + 1)
    }
    if (kind === "VP8 ") {
      if (length < 10 || byteString(bytes, body + 3, 3) !== "\x9d\x01\x2a") invalid()
      return dimensions(view.getUint16(body + 6, true) & 0x3fff, view.getUint16(body + 8, true) & 0x3fff)
    }
    if (kind === "VP8L") {
      if (length < 5 || bytes[body] !== 0x2f) invalid()
      const packed = view.getUint32(body + 1, true)
      return dimensions((packed & 0x3fff) + 1, ((packed >>> 14) & 0x3fff) + 1)
    }
    offset = body + length + (length % 2)
  }
  return invalid()
}

/** Check dimensions before allocating a decoded bitmap. Server checks remain authoritative. */
export function imageHeader(bytes: Uint8Array, type: string): ImageDimensions {
  switch (type) {
    case "image/png": return png(bytes)
    case "image/jpeg": return jpeg(bytes)
    case "image/webp": return webp(bytes)
    default: return invalid("请选择 JPG、PNG 或 WebP 图片。")
  }
}

function cancelled(signal?: AbortSignal): void {
  if (signal?.aborted) throw new DOMException("Upload cancelled", "AbortError")
}

/** Decode only after bounded header inspection; close/revoke every resource. */
export async function inspectAvatar(file: File, signal?: AbortSignal): Promise<ImageDimensions> {
  cancelled(signal)
  if (file.size > 5 * 1024 * 1024) {
    throw new ApiError(413, "image_too_large", "图片不能超过 5 MB。")
  }
  if (!file.size) invalid("图片是空的，请重新选择。")
  const bytes = new Uint8Array(await readImageBytes(file, signal))
  cancelled(signal)
  imageHeader(bytes, file.type)
  if (typeof createImageBitmap === "function") {
    let bitmap: ImageBitmap
    try {
      bitmap = await createImageBitmap(file)
    } catch {
      cancelled(signal)
      return invalid()
    }
    try {
      cancelled(signal)
      return dimensions(bitmap.width, bitmap.height)
    } finally {
      bitmap.close()
    }
  }
  return inspectWithImage(file, signal)
}

function inspectWithImage(file: File, signal?: AbortSignal): Promise<ImageDimensions> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    const url = URL.createObjectURL(file)
    let settled = false
    function finish(action: () => void): void {
      if (settled) return
      settled = true
      image.onload = null
      image.onerror = null
      signal?.removeEventListener("abort", abort)
      URL.revokeObjectURL(url)
      image.src = ""
      action()
    }
    function abort(): void {
      finish(() => reject(new DOMException("Upload cancelled", "AbortError")))
    }
    image.onload = () => {
      const width = image.naturalWidth
      const height = image.naturalHeight
      finish(() => {
        try { resolve(dimensions(width, height)) } catch (error) { reject(error) }
      })
    }
    image.onerror = () => finish(() => {
      reject(new ApiError(422, "invalid_image", "无法读取这张图片，请重新选择。"))
    })
    signal?.addEventListener("abort", abort, { once: true })
    if (signal?.aborted) abort()
    else image.src = url
  })
}

/** FileReader can cancel the header read when the upload form unmounts. */
function readImageBytes(file: File, signal?: AbortSignal): Promise<ArrayBuffer> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    let finished = false
    function settle(action: () => void): void {
      if (finished) return
      finished = true
      reader.onload = null
      reader.onerror = null
      reader.onabort = null
      signal?.removeEventListener("abort", abort)
      action()
    }
    function abort(): void {
      reader.abort()
      settle(() => reject(new DOMException("Upload cancelled", "AbortError")))
    }
    reader.onload = () => {
      const bytes = reader.result
      settle(() => {
        if (bytes instanceof ArrayBuffer) resolve(bytes)
        else reject(new ApiError(422, "invalid_image", "无法读取这张图片，请重新选择。"))
      })
    }
    reader.onerror = () => settle(() => {
      reject(new ApiError(0, "file_read_failed", "无法读取这张图片，请重新选择。"))
    })
    reader.onabort = () => settle(() => {
      reject(new DOMException("Upload cancelled", "AbortError"))
    })
    signal?.addEventListener("abort", abort, { once: true })
    if (signal?.aborted) {
      abort()
      return
    }
    try {
      reader.readAsArrayBuffer(file)
    } catch {
      settle(() => reject(new ApiError(0, "file_read_failed", "无法读取这张图片，请重新选择。")))
    }
  })
}
