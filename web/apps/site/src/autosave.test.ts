import { afterEach, expect, test, vi } from "vitest"
import { ApiError } from "@sjtu-ow/api"
import { Autosave, SaveQueue } from "@sjtu-ow/shared/autosave"
import type { SaveTransport } from "@sjtu-ow/shared/autosave"
import { primitiveValues, readSaveReceipt } from "@sjtu-ow/shared/save-receipt"

afterEach(() => vi.useRealTimers())
const initial = { nickname: "成员", motto: "原宣言", show_rank: false }
function setup(transport: SaveTransport<typeof initial>) {
  let key = 0
  return new Autosave({ initial, version: 3, transport, newKey: () => `key-${++key}`, readCurrent: (value) => {
    const current = value as { version: number; values: typeof initial }
    return current?.values ? current : null
  } })
}

test("autosave sends only edits and preserves a false privacy preference", async () => {
  const transport = vi.fn<SaveTransport<typeof initial>>(async () => ({ version: 4, saved: ["motto"] }))
  const save = setup(transport)
  save.set("motto", "新宣言")
  expect(await save.flush()).toBe(true)
  expect(transport.mock.calls[0][0]).toEqual({ base_version: 3, changes: { motto: "新宣言" } })
  expect(save.snapshot().values.show_rank).toBe(false)
  save.dispose()
})

test("edits during a flight use the next version and never overlap requests", async () => {
  let release: (() => void) | undefined
  let calls = 0
  const transport = vi.fn<SaveTransport<typeof initial>>(async () => {
    calls += 1
    if (calls === 1) await new Promise<void>((resolve) => { release = resolve })
    return { version: 3 + calls, saved: ["motto"] }
  })
  const save = setup(transport)
  save.set("motto", "第一次")
  const pending = save.flush()
  await Promise.resolve()
  save.set("motto", "第二次")
  expect(transport).toHaveBeenCalledTimes(1)
  release?.()
  expect(await pending).toBe(true)
  expect(transport).toHaveBeenCalledTimes(2)
  expect(transport.mock.calls[1][0]).toEqual({ base_version: 4, changes: { motto: "第二次" } })
  save.dispose()
})

test("uncertain responses retry the identical body and key before later edits", async () => {
  vi.useFakeTimers()
  let calls = 0
  const transport = vi.fn<SaveTransport<typeof initial>>(async () => {
    if (++calls === 1) throw new ApiError(0, "network", "网络断开")
    return { version: 3 + calls, saved: ["motto"] }
  })
  const save = setup(transport)
  save.set("motto", "第一次")
  expect(await save.flush()).toBe(false)
  save.set("motto", "第二次")
  await vi.advanceTimersByTimeAsync(5000)
  expect(transport.mock.calls[1][0]).toEqual(transport.mock.calls[0][0])
  expect(transport.mock.calls[1][1]).toBe(transport.mock.calls[0][1])
  expect(transport.mock.calls[2][0]).toMatchObject({ changes: { motto: "第二次" } })
  expect(transport.mock.calls[2][1]).not.toBe(transport.mock.calls[0][1])
  expect(save.snapshot().dirty).toBe(false)
  save.dispose()
})

test("partial receipts retain invalid draft fields without a resubmit loop", async () => {
  const transport = vi.fn<SaveTransport<typeof initial>>(async () => ({ version: 4, saved: ["motto"], fields: { nickname: ["太短"] } }))
  const save = setup(transport)
  save.setMany({ motto: "合法", nickname: "短" })
  expect(await save.flush()).toBe(false)
  expect(transport).toHaveBeenCalledTimes(1)
  expect(save.snapshot()).toMatchObject({ state: "partial", dirty: true, fields: { nickname: ["太短"] } })
  expect(save.snapshot().committed.nickname).toBe("成员")
  expect(save.snapshot().values.nickname).toBe("短")
  save.dispose()
})

test("409 replaces all editable values with actual current values", async () => {
  const error = new ApiError(409, "stale", "冲突")
  error.current = { version: 8, values: { ...initial, motto: "其他标签页" } }
  const save = setup(async () => { throw error })
  save.set("motto", "本地")
  await save.flush()
  expect(save.snapshot()).toMatchObject({ version: 8, dirty: false, values: { motto: "其他标签页", show_rank: false } })
  save.dispose()
})

test("missing versioned capability never invokes the old full-form endpoint", async () => {
  const transport = vi.fn<SaveTransport<typeof initial>>(async () => ({ version: 4, saved: ["motto"] }))
  const save = new Autosave({ initial, version: 0, available: () => false, transport, readCurrent: () => null })
  save.set("motto", "本地")
  expect(await save.flush()).toBe(false)
  expect(transport).not.toHaveBeenCalled()
  expect(save.snapshot().dirty).toBe(true)
  save.dispose()
})

test("429 respects Retry-After and disposal cancels future retries", async () => {
  vi.useFakeTimers()
  const error = new ApiError(429, "rate_limited", "太快")
  error.retryAfter = 30
  const transport = vi.fn<SaveTransport<typeof initial>>(async () => { throw error })
  const save = setup(transport)
  save.set("motto", "本地")
  await save.flush()
  await vi.advanceTimersByTimeAsync(29_000)
  expect(transport).toHaveBeenCalledTimes(1)
  save.dispose()
  await vi.advanceTimersByTimeAsync(31_000)
  expect(transport).toHaveBeenCalledTimes(1)
})

test("shared queue advances after a failure", async () => {
  const queue = new SaveQueue()
  const first = queue.run(async () => { throw new Error("failed") })
  const second = queue.run(async () => "next")
  await expect(first).rejects.toThrow("failed")
  await expect(second).resolves.toBe("next")
})

test("receipt parser rejects legacy success, invalid values and contradictory errors", () => {
  const validator = primitiveValues(initial)
  for (const receipt of [
    { result: "ok" },
    { version: -1, saved: [] },
    { version: 4, saved: ["unknown"] },
    { version: 4, saved: ["motto", "motto"] },
    { version: 4, saved: ["motto"], fields: { motto: ["失败"] } },
    { version: 4, saved: ["show_rank"], values: { show_rank: "true" } },
  ]) expect(() => readSaveReceipt(receipt, initial, validator)).toThrow()
})
