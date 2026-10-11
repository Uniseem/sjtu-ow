import { expect, test } from "vitest"
import { imageHeader } from "./image-inspect"

function png(width: number, height: number): Uint8Array {
  const bytes = new Uint8Array(33)
  bytes.set([137, 80, 78, 71, 13, 10, 26, 10])
  const view = new DataView(bytes.buffer)
  view.setUint32(8, 13)
  bytes.set([73, 72, 68, 82], 12)
  view.setUint32(16, width)
  view.setUint32(20, height)
  return bytes
}

test("avatar header rejects small images and decompression-size limits before decoding", () => {
  expect(imageHeader(png(128, 128), "image/png")).toEqual({ width: 128, height: 128 })
  expect(() => imageHeader(png(127, 128), "image/png")).toThrow("至少")
  expect(() => imageHeader(png(10_000, 10_000), "image/png")).toThrow("4000")
  expect(() => imageHeader(new Uint8Array(8), "image/png")).toThrow()
  expect(() => imageHeader(png(128, 128), "image/jpeg")).toThrow()
})

test("JPEG marker parsing handles metadata and rejects truncated length", () => {
  const bytes = new Uint8Array([255,216,255,224,0,4,0,0,255,192,0,8,8,1,0,2,0,1])
  expect(imageHeader(bytes, "image/jpeg")).toEqual({ width: 512, height: 256 })
  bytes[5] = 255
  expect(() => imageHeader(bytes, "image/jpeg")).toThrow()
})

test("WebP extended header preserves zero-based dimensions and enforces RIFF bounds", () => {
  const bytes = new Uint8Array(30)
  bytes.set([..."RIFF"].map((c) => c.charCodeAt(0)))
  bytes.set([..."WEBPVP8X"].map((c) => c.charCodeAt(0)), 8)
  const view = new DataView(bytes.buffer)
  view.setUint32(4, 22, true)
  view.setUint32(16, 10, true)
  bytes[24] = 127
  bytes[27] = 127
  expect(imageHeader(bytes, "image/webp")).toEqual({ width: 128, height: 128 })
  view.setUint32(16, 100, true)
  expect(() => imageHeader(bytes, "image/webp")).toThrow()
})
